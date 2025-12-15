# cython: language_level=3
from cpython.object cimport PyObject
from cpython.ref cimport Py_INCREF, Py_XINCREF
from libc.string cimport memcpy

# =============================================================================
# C-API 黑魔法定义区 (解决 PyTypeObject 属性不可访问问题)
# =============================================================================
cdef extern from "Python.h":
    # 1. 定义成员描述符结构体
    ctypedef struct PyMemberDef:
        char *name
        int type
        int offset
        int flags
        char *doc

    # 2. 定义分配函数指针类型
    ctypedef PyObject* (*allocfunc)(void *type, Py_ssize_t nitems)

    # 3. 自定义 TypeObject 结构体 (映射 C 的 PyTypeObject)
    # 通过这个结构体，我们可以访问 tp_alloc 和 tp_members
    ctypedef struct RawTypeObject "PyTypeObject":
        Py_ssize_t tp_basicsize
        Py_ssize_t tp_itemsize
        allocfunc tp_alloc        # 关键：暴露分配函数
        PyMemberDef *tp_members   # 关键：暴露成员列表

    # 4. 字段类型常量
    int T_OBJECT
    int T_OBJECT_EX
    
    # 获取对象的类型指针 (返回我们的自定义结构体指针)
    RawTypeObject* Py_TYPE(object ob)

# =============================================================================
# Event 实现
# =============================================================================

cdef class Event:
    def __init__(self, long long timestamp):
        self.timestamp = timestamp
        self.source = 0
        self.producer = 0

    def __lt__(self, Event other):
        return self.timestamp < other.timestamp

    # 【核心】通用的 C 级别 Clone 方法 (Memcpy 版本)
    cdef Event _c_clone(self):
        # 1. 获取底层类型指针
        cdef RawTypeObject *tp = Py_TYPE(self)
        cdef PyObject *src = <PyObject *>self
        cdef PyObject *dst
        cdef PyMemberDef *members
        cdef char *addr
        cdef PyObject **obj_ptr
        cdef int i

        # 2. 分配内存 (调用 tp->tp_alloc)
        # 相当于绕过了 __init__，直接申请了一块干净的内存
        dst = tp.tp_alloc(tp, 0)
        if dst == NULL:
            raise MemoryError("Failed to allocate memory for event clone")

        # 3. 内存拷贝 (memcpy)
        # 这一步将所有字段（int, float, char*, PyObject* 等）的二进制位完全复制
        memcpy(dst, src, tp.tp_basicsize)

        # 4. 修正对象引用计数 (Fix RefCounts)
        # 必须遍历类型定义的成员列表，找到所有 Python 对象类型的字段，手动 INCREF
        members = tp.tp_members
        if members != NULL:
            i = 0
            while members[i].name != NULL:
                # T_OBJECT (6) 和 T_OBJECT_EX (16) 代表 Python 对象
                if members[i].type == T_OBJECT or members[i].type == T_OBJECT_EX:
                    # 计算字段在结构体中的内存地址
                    addr = <char *>dst + members[i].offset
                    obj_ptr = <PyObject **>addr
                    
                    # 如果该字段不为空 (PyObject* 不为 NULL)
                    if obj_ptr[0] != NULL:
                        # 【关键修复】强制转换为 <object>，让 Cython 接受它作为 Py_INCREF 的参数
                        Py_INCREF(<object>obj_ptr[0])
                i += 1
        
        # 将 C 指针转回 Cython 对象包装
        return <Event>dst

    # 暴露给 Python 和 Cython 的 derive 接口
    cpdef Event derive(self):
        # 1. 调用通用拷贝
        cdef Event new_event = self._c_clone()
        
        # 2. 重置 Event 头部信息
        new_event.timestamp = 0
        new_event.source = 0
        new_event.producer = 0
        
        return new_event