/*

    Sartorial Programming Interface (SPI) runtime libraries
    Copyright (C) 2012-2023 Sartorial Programming Ltd.

    This library is free software; you can redistribute it and/or
    modify it under the terms of the GNU Lesser General Public
    License as published by the Free Software Foundation; either
    version 2.1 of the License, or (at your option) any later version.

    This library is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public
    License along with this library; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301
    USA

*/
/*
***************************************************************************
** pyDate.cpp
**
** Primitive Python date conversion routines.
**
** Only this module accesses the Python DateTime module.
***************************************************************************
*/

#include "../pyDate.hpp"
#include "../pyUtil.hpp"
#include "pyVersion.hpp"

// extra python headers
#include <datetime.h>

#include <spi/RuntimeError.hpp>
#include <spi/Map.hpp>

#ifdef Py_LIMITED_API
// datetime's private capsule layout is not part of either Stable ABI.
static PyObject* dateType = NULL;
static PyObject* dateTimeType = NULL;
#define PyDate_Check(op) PyObject_TypeCheck(op, (PyTypeObject*)dateType)
#define PyDateTime_Check(op) PyObject_TypeCheck(op, (PyTypeObject*)dateTimeType)
#define PyDate_FromDate(y, m, d) PyObject_CallFunction(dateType, "iii", y, m, d)
#define PyDateTime_FromDateAndTime(y, m, d, h, min, sec, us) \
    PyObject_CallFunction(dateTimeType, "iiiiiii", y, m, d, h, min, sec, us)
#endif

SPI_BEGIN_NAMESPACE

namespace
{

#ifdef Py_LIMITED_API
    int pyoGetIntAttribute(PyObject* pyo, const char* attr)
    {
        PyObject* v = PyObject_GetAttrString(pyo, attr);
        if (!v)
            throw PyException();
        int result = (int)PyLong_AsLong(v);
        PYO_DECREF(v);
        if (PyErr_Occurred())
            throw PyException();
        return result;
    }
#endif

    /**
     * Ensures that the datetime module gets imported.
     */
    void pyImportDateTime(void)
    {
        static bool imported = false;

        if (!imported)
        {
#ifdef Py_LIMITED_API
            PyObjectSP module = pyoShare(PyImport_ImportModule("datetime"));
            if (!module) throw PyException();
            PyObjectSP date = pyoShare(PyObject_GetAttrString(module.get(), "date"));
            PyObjectSP datetime = pyoShare(PyObject_GetAttrString(module.get(), "datetime"));
            if (!date || !datetime) throw PyException();
            dateType = pyoRelease(date);
            dateTimeType = pyoRelease(datetime);
#else
            PyDateTime_IMPORT;
            if (!PyDateTimeAPI) throw PyException();
#endif
            imported = true;
        }
    }

    int pyDateTime_GetYear(PyObject* pyo)
    {
#ifdef Py_LIMITED_API
        return pyoGetIntAttribute(pyo, "year");
#else
        return PyDateTime_GET_YEAR(pyo);
#endif
    }

    int pyDateTime_GetMonth(PyObject* pyo)
    {
#ifdef Py_LIMITED_API
        return pyoGetIntAttribute(pyo, "month");
#else
        return PyDateTime_GET_MONTH(pyo);
#endif
    }

    int pyDateTime_GetDay(PyObject* pyo)
    {
#ifdef Py_LIMITED_API
        return pyoGetIntAttribute(pyo, "day");
#else
        return PyDateTime_GET_DAY(pyo);
#endif
    }

    int pyDateTime_GetSecond(PyObject* pyo)
    {
#ifdef Py_LIMITED_API
        return pyoGetIntAttribute(pyo, "second");
#else
        return PyDateTime_DATE_GET_SECOND(pyo);
#endif
    }

    int pyDateTime_GetMinute(PyObject* pyo)
    {
#ifdef Py_LIMITED_API
        return pyoGetIntAttribute(pyo, "minute");
#else
        return PyDateTime_DATE_GET_MINUTE(pyo);
#endif
    }

    int pyDateTime_GetHour(PyObject* pyo)
    {
#ifdef Py_LIMITED_API
        return pyoGetIntAttribute(pyo, "hour");
#else
        return PyDateTime_DATE_GET_HOUR(pyo);
#endif
    }

} // end of anonymous namespace

bool pyIsDate(PyObject* pyo)
{
    pyImportDateTime();

    if (PyDate_Check(pyo))
        return true;

    return false;
}

bool pyIsDateTime(PyObject* pyo)
{
    pyImportDateTime();

    if (PyDateTime_Check(pyo))
        return true;

    return false;
}

PyObject* pyMakeDate(int year, int month, int day)
{
    pyImportDateTime();

    return PyDate_FromDate(year, month, day);
}

PyObject* pyMakeDateTime(int year, int month, int day,
    int hours, int minutes, int seconds)
{
    pyImportDateTime();

    return PyDateTime_FromDateAndTime(year, month, day,
        hours, minutes, seconds, 0);
}

Date pyToDate(PyObject* pyo)
{
    if (pyIsDate(pyo))
    {
#ifdef Py_LIMITED_API
        PyObjectSP r = pyoShare(PyObject_CallMethod(pyo, "toordinal", NULL));
        if (!r)
            throw PyException();
        long ord = PyLong_AsLong(r.get());
        if (ord == -1 && PyErr_Occurred())
            throw PyException();
        return Date(ord - 584389);
#else
        int year  = pyDateTime_GetYear(pyo);
        int month = pyDateTime_GetMonth(pyo);
        int day   = pyDateTime_GetDay(pyo);

        return Date(year, month, day);
#endif
    }

    throw RuntimeError("%s: Input is not a date", __FUNCTION__);
}

DateTime pyToDateTime(PyObject* pyo)
{
    if (pyIsDateTime(pyo))
    {
        int year  = pyDateTime_GetYear(pyo);
        int month = pyDateTime_GetMonth(pyo);
        int day   = pyDateTime_GetDay(pyo);

        Date date(year, month, day);

        int hours   = pyDateTime_GetHour(pyo);
        int minutes = pyDateTime_GetMinute(pyo);
        int seconds = pyDateTime_GetSecond(pyo);

        return DateTime(date, hours, minutes, seconds);
    }

    throw RuntimeError("%s: Input is not a dateTime", __FUNCTION__);
}

SPI_END_NAMESPACE

