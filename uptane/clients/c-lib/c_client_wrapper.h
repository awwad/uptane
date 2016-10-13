/*
 *
 * Wrapper for C CAN comunication module.  
 *
 */

#ifndef C_CLIENT_WRAPPER_H
#define C_CLIENT_WRAPPER_H

#include "libuptane.h"
#include <python2.7/Python.h>

/*
 * Wrapper function to be called from Python.
 */
static PyObject* py_send_isotp_file_wrapper(PyObject* self, PyObject* args) {
  int target = 0;
  int data_type = 0; 
  char *filename = NULL;
  PyArg_ParseTuple(args, "iis", &target, &data_type, &filename);
  /*
   * Call C function
   */
  send_isotp_file(target, data_type, filename);

  return Py_BuildValue();
}

/*
 * Bind Python function names to our C functions.
 */
static PyMethodDef Module_methods[] = {
  {"send_isotp_file_wrapper", py_send_isotp_file_wrapper, METH_VARARGS},
  {NULL, NULL}
};

/*
 * Python calls this to let us initialize our module.
 */
void initpyfoo() {
  (void) Py_InitModule("pyfoo", Module_methods);
}

#endif
