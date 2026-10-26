//! The tokenizer of Sift in Rust: the module `sift._rs`.
//!
//! The functions take text that `sift.analysis.tokenize.fold` has
//! already normalized (NFKC and casefold) and return the tokens that
//! `iter_tokens` yields for the original text. NFKC and casefold stay
//! in Python: no Rust crate implements `str.casefold` for the Unicode
//! version of the interpreter, so the Python side does them, like in
//! the C versions.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::thread;

/// A token: text, position, start and end in characters (end exclusive).
type Token = (String, u32, u32, u32);

/// The most threads `tokenize_many` accepts.
const MAX_THREADS: usize = 256;

fn is_latin(c: char) -> bool {
    matches!(c, '0'..='9' | 'a'..='z' | '_')
}

/// The CJK ranges of `src/sift/analysis/tokenize.py`.
fn is_cjk(c: char) -> bool {
    matches!(c, '\u{3400}'..='\u{4dbf}' | '\u{4e00}'..='\u{9fff}' | '\u{f900}'..='\u{faff}')
}

/// The tokens of `text`, which is NFKC and casefolded already.
///
/// A character offset is a count of `char`s, which is what a Python
/// `str` offset counts. Texts of more than `u32::MAX` characters are
/// the caller's to refuse (see `check_len`).
fn tokens(text: &str) -> Vec<Token> {
    let mut out = Vec::new();
    let mut chars = text.char_indices().peekable();
    // Byte offsets of the characters of the CJK run being read, then
    // the offset just past the run.
    let mut run: Vec<usize> = Vec::new();
    let mut at: u32 = 0;
    let mut position: u32 = 0;

    while let Some((start, c)) = chars.next() {
        let first = at;
        at += 1;
        if is_latin(c) {
            let mut end = start + c.len_utf8();
            while let Some(&(i, next)) = chars.peek() {
                if !is_latin(next) {
                    break;
                }
                end = i + next.len_utf8();
                at += 1;
                chars.next();
            }
            // A suffix: `+`, `++` or `#`, as in c++ and c#.
            if let Some(&(i, '+')) = chars.peek() {
                end = i + 1;
                at += 1;
                chars.next();
                if let Some(&(j, '+')) = chars.peek() {
                    end = j + 1;
                    at += 1;
                    chars.next();
                }
            } else if let Some(&(i, '#')) = chars.peek() {
                end = i + 1;
                at += 1;
                chars.next();
            }
            out.push((text[start..end].to_owned(), position, first, at));
            position += 1;
        } else if is_cjk(c) {
            run.clear();
            run.push(start);
            let mut end = start + c.len_utf8();
            while let Some(&(i, next)) = chars.peek() {
                if !is_cjk(next) {
                    break;
                }
                run.push(i);
                end = i + next.len_utf8();
                at += 1;
                chars.next();
            }
            run.push(end);
            if run.len() == 2 {
                out.push((text[start..end].to_owned(), position, first, at));
                position += 1;
                continue;
            }
            // `run` holds the starts of the n characters and then the
            // end of the run: n - 1 bigrams, the last one ends at run[n].
            for i in 0..run.len() - 2 {
                let bigram = &text[run[i]..run[i + 2]];
                let from = first + i as u32;
                out.push((bigram.to_owned(), position, from, from + 2));
                position += 1;
            }
        }
    }
    out
}

/// Refuse a text whose offsets would not fit in a `u32`.
fn check_len(text: &str) -> PyResult<()> {
    if text.len() > u32::MAX as usize {
        return Err(PyValueError::new_err(format!(
            "text of {} bytes is too long, the limit is {}",
            text.len(),
            u32::MAX
        )));
    }
    Ok(())
}

/// Tokenize `texts` on `threads` threads, results in the order of `texts`.
///
/// The threads take the next unread text from a shared counter, so a
/// few long posts do not leave the others idle.
fn tokens_many(texts: &[String], threads: usize) -> Vec<Vec<Token>> {
    let next = AtomicUsize::new(0);
    let worker = || {
        let mut done: Vec<(usize, Vec<Token>)> = Vec::new();
        loop {
            let i = next.fetch_add(1, Ordering::Relaxed);
            let Some(text) = texts.get(i) else {
                break done;
            };
            done.push((i, tokens(text)));
        }
    };
    let parts: Vec<Vec<(usize, Vec<Token>)>> = if threads <= 1 {
        vec![worker()]
    } else {
        thread::scope(|scope| {
            let handles: Vec<_> = (0..threads).map(|_| scope.spawn(worker)).collect();
            handles
                .into_iter()
                .map(|handle| {
                    handle
                        .join()
                        .unwrap_or_else(|panic| std::panic::resume_unwind(panic))
                })
                .collect()
        })
    };
    let mut out = vec![Vec::new(); texts.len()];
    for (i, found) in parts.into_iter().flatten() {
        out[i] = found;
    }
    out
}

/// Return the tokens of `text` as (text, position, start, end) tuples.
///
/// `text` must be NFKC-normalized and casefolded. Offsets count
/// characters, end exclusive. A lone surrogate raises UnicodeEncodeError;
/// `sift.ext.rs` replaces them first. ValueError if the text is longer
/// than 4 GiB.
#[pyfunction]
fn tokenize(text: &str) -> PyResult<Vec<Token>> {
    check_len(text)?;
    Ok(tokens(text))
}

/// Return `tokenize(text)` for every text, with the GIL released.
///
/// `threads` is the number of Rust threads: 0 means one per CPU, and
/// more than 256 raises ValueError.
#[pyfunction]
#[pyo3(signature = (texts, threads = 0))]
fn tokenize_many(py: Python<'_>, texts: Vec<String>, threads: usize) -> PyResult<Vec<Vec<Token>>> {
    if threads > MAX_THREADS {
        return Err(PyValueError::new_err(format!(
            "threads must be between 0 and {MAX_THREADS}, got {threads}"
        )));
    }
    texts.iter().try_for_each(|text| check_len(text))?;
    let threads = match threads {
        0 => thread::available_parallelism().map_or(1, usize::from),
        n => n,
    };
    let threads = threads.min(texts.len().max(1));
    Ok(py.detach(move || tokens_many(&texts, threads)))
}

/// Panic on purpose, to see how PyO3 maps a Rust panic. Debug builds only.
#[cfg(debug_assertions)]
#[pyfunction]
fn panic_for_lab(message: &str) {
    panic!("{message}");
}

#[pymodule]
fn _rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(tokenize, m)?)?;
    m.add_function(wrap_pyfunction!(tokenize_many, m)?)?;
    #[cfg(debug_assertions)]
    m.add_function(wrap_pyfunction!(panic_for_lab, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn latin_keeps_its_suffix() {
        let got = tokens("c++ c# c+++ a_b 9+");
        let want: Vec<Token> = vec![
            ("c++".into(), 0, 0, 3),
            ("c#".into(), 1, 4, 6),
            ("c++".into(), 2, 7, 10),
            ("a_b".into(), 3, 12, 15),
            ("9+".into(), 4, 16, 18),
        ];
        assert_eq!(got, want);
        assert!(tokens("").is_empty());
    }

    #[test]
    fn cjk_runs_become_bigrams() {
        let got = tokens("中a搜索引擎");
        let want: Vec<Token> = vec![
            ("中".into(), 0, 0, 1),
            ("a".into(), 1, 1, 2),
            ("搜索".into(), 2, 2, 4),
            ("索引".into(), 3, 3, 5),
            ("引擎".into(), 4, 4, 6),
        ];
        assert_eq!(got, want);
    }
}
