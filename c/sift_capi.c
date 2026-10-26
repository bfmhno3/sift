// SPDX-License-Identifier: MIT OR Apache-2.0
/*
 * sift_capi.c: sift.ext._capi, a CPython extension module written
 * against the C API.
 *
 *	count_cjk(text: str) -> int
 *
 * counts the CJK characters of text (the ranges of sift_tok.c). It
 * reads the characters of the str in place, in whatever width the
 * str stores them, so nothing is encoded or copied.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>

/*
 * A scan this long drops the GIL: other threads run while it counts.
 * Shorter ones are faster with the GIL held, the release and the
 * re-acquire cost more than the scan.
 */
#define NOGIL_MIN	(1 << 16)

static int is_cjk(Py_UCS4 c)
{
	return (c >= 0x3400 && c <= 0x4dbf) ||
	       (c >= 0x4e00 && c <= 0x9fff) ||
	       (c >= 0xf900 && c <= 0xfaff);
}

static Py_ssize_t count_ucs2(const Py_UCS2 *s, Py_ssize_t len)
{
	Py_ssize_t i;
	Py_ssize_t count = 0;

	for (i = 0; i < len; i++)
		count += is_cjk(s[i]);
	return count;
}

static Py_ssize_t count_ucs4(const Py_UCS4 *s, Py_ssize_t len)
{
	Py_ssize_t i;
	Py_ssize_t count = 0;

	for (i = 0; i < len; i++)
		count += is_cjk(s[i]);
	return count;
}

/*
 * arg is a borrowed reference: the caller's frame keeps the str alive
 * for the whole call, even while the GIL is released, and a str never
 * changes. The result is a new reference, which the caller owns.
 */
static PyObject *capi_count_cjk(PyObject *module, PyObject *arg)
{
	Py_ssize_t len;
	Py_ssize_t count = 0;
	int kind;
	const void *data;

	(void)module;
	if (!PyUnicode_Check(arg)) {
		PyErr_Format(PyExc_TypeError,
			     "count_cjk() argument must be str, not %.100s",
			     Py_TYPE(arg)->tp_name);
		return NULL;
	}
	len = PyUnicode_GET_LENGTH(arg);
	kind = PyUnicode_KIND(arg);
	data = PyUnicode_DATA(arg);

	/* Latin-1 text has no CJK: its characters are below U+0100. */
	if (kind == PyUnicode_1BYTE_KIND)
		return PyLong_FromSsize_t(0);

	if (len >= NOGIL_MIN) {
		Py_BEGIN_ALLOW_THREADS
		count = kind == PyUnicode_2BYTE_KIND ?
			count_ucs2(data, len) : count_ucs4(data, len);
		Py_END_ALLOW_THREADS
	} else {
		count = kind == PyUnicode_2BYTE_KIND ?
			count_ucs2(data, len) : count_ucs4(data, len);
	}
	return PyLong_FromSsize_t(count);
}

static PyMethodDef capi_methods[] = {
	{"count_cjk", capi_count_cjk, METH_O,
	 PyDoc_STR("count_cjk(text, /)\n--\n\n"
		   "Return the number of CJK characters in text.")},
	{NULL, NULL, 0, NULL},
};

static PyModuleDef_Slot capi_slots[] = {
	{Py_mod_multiple_interpreters, Py_MOD_PER_INTERPRETER_GIL_SUPPORTED},
	{Py_mod_gil, Py_MOD_GIL_NOT_USED},
	{0, NULL},
};

static struct PyModuleDef capi_module = {
	.m_base = PyModuleDef_HEAD_INIT,
	.m_name = "_capi",
	.m_doc = PyDoc_STR("C API functions of Sift."),
	.m_size = 0,
	.m_methods = capi_methods,
	.m_slots = capi_slots,
};

PyMODINIT_FUNC PyInit__capi(void)
{
	return PyModuleDef_Init(&capi_module);
}
