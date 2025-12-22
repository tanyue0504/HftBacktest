# 运行时执行以下命令以编译 Cython 模块
# python setup.py build_ext --inplace
# HFT_DEBUG=1 python setup.py build_ext --inplace
# rm -rf build/ hft_backtest/*.so hft_backtest/*.cpp hft_backtest/*.c
# 生成pyi文件 
# stubgen -m hft_backtest.order -o .
# stubgen -m hft_backtest.event -o .
import os
import numpy # 需要导入 numpy 以获取 include 路径
from setuptools import setup, find_packages, Extension
from Cython.Build import cythonize

# 检查环境变量开启 Debug
DEBUG_MODE = os.environ.get("HFT_DEBUG") == "1"

# 1. 定义基础指令
compiler_directives = {
    'language_level': "3",
    'embedsignature': True,
    'binding': True,  # 必须为 True 才能让函数绑定到 Python (对于 Debug 也是必须的)
}

# 2. 定义宏列表
define_macros = []
if DEBUG_MODE:
    print("⚠️  BUILDING IN DEBUG MODE (Linetrace Enabled) ⚠️")
    
    # 【Python 3.10 黄金配置】
    compiler_directives['linetrace'] = True
    compiler_directives['binding'] = True   # <--- 3.10 必须开启 binding！
    # compiler_directives['profile'] = True # <--- 删掉或注释掉这行，不需要
    
    # 宏定义
    define_macros.append(('CYTHON_TRACE', '1'))
    define_macros.append(('CYTHON_TRACE_NOGIL', '1'))
else:
    print("🚀 BUILDING IN PERFORMANCE MODE 🚀")

# 3. 定义扩展模块
# 【关键修复】必须将 define_macros 传递给每一个 Extension
extensions = [
    Extension(
        "hft_backtest.event", 
        ["hft_backtest/event.pyx"],
        define_macros=define_macros, # <--- 新增
    ),
    Extension(
        "hft_backtest.order",
        ["hft_backtest/order.pyx"],
        define_macros=define_macros, # <--- 新增
    ),
    Extension(
        "hft_backtest.event_engine", 
        ["hft_backtest/event_engine.pyx"],
        define_macros=define_macros, # <--- 新增
    ),
    Extension(
        "hft_backtest.delaybus", 
        ["hft_backtest/delaybus.pyx"],
        # include_dirs=[numpy.get_include()],
        language="c++",  # <--- 必须有这一行，因为用了 libcpp.vector
        define_macros=define_macros, # <--- 新增
    ),
    Extension(
        "hft_backtest.merged_dataset",
        ["hft_backtest/merged_dataset.pyx"],
        language="c++",
        define_macros=define_macros, # <--- 新增
    ),
    Extension(
        "hft_backtest.reader", 
        ["hft_backtest/reader.pyx"],
        define_macros=define_macros, # <--- 新增
    ),
    Extension(
        "hft_backtest.backtest", 
        ["hft_backtest/backtest.pyx"], 
        language="c++",
        define_macros=define_macros, # <--- 新增
    ),
    Extension(
        "hft_backtest.okx.event",  # <--- 新模块
        ["hft_backtest/okx/event.pyx"],
        define_macros=define_macros,
    ),
]

setup(
    name="hft_backtest",  # 包名
    version="0.1.0",
    description="A high-performance event-driven high-frequency trading backtesting framework.",
    author="Tan yue <1752633783@qq.com>",   # 建议填写作者
    packages=find_packages(),  # 自动发现包目录
    
    # 定义运行时依赖
    install_requires=[
        "numpy",
        "pandas",
        "pyarrow",
        "loguru",
        "Cython",  # 因为代码中使用了 pyximport，需要运行时包含 Cython
    ],
    
    # 编译配置
    # 【关键修复】这里要使用上面动态修改过的 compiler_directives 变量
    # 原代码错误：ext_modules=cythonize(extensions, compiler_directives={'language_level': "3", ...}),
    ext_modules=cythonize(
        extensions, 
        compiler_directives=compiler_directives, # <--- 使用变量
        # gdb_debug=True # 如果需要底层 C 调试可以打开
    ),
    
    zip_safe=False,
    
    # 包含 numpy 头文件，防止某些组件编译找不到头文件
    include_dirs=[numpy.get_include()],
    
    # 原代码中多余的参数，setup 函数本身不直接接收 compiler_directives
    # compiler_directives=compiler_directives, 
)