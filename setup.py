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
    compiler_directives['linetrace'] = True
    compiler_directives['binding'] = True
    define_macros.append(('CYTHON_TRACE', '1'))
    define_macros.append(('CYTHON_TRACE_NOGIL', '1'))
else:
    print("🚀 BUILDING IN PERFORMANCE MODE 🚀")

# 3. 定义扩展模块
extensions = [
    Extension(
        "hft_backtest.event", 
        ["hft_backtest/event.pyx"],
        define_macros=define_macros,
    ),
    Extension(
        "hft_backtest.order",
        ["hft_backtest/order.pyx"],
        define_macros=define_macros,
    ),
    Extension(
        "hft_backtest.event_engine", 
        ["hft_backtest/event_engine.pyx"],
        define_macros=define_macros,
    ),
    Extension(
        "hft_backtest.matcher", 
        ["hft_backtest/matcher.pyx"],
        define_macros=define_macros,
    ),
    Extension(
        "hft_backtest.delaybus", 
        ["hft_backtest/delaybus.pyx"],
        language="c++",
        define_macros=define_macros,
    ),
    Extension(
        "hft_backtest.merged_dataset",
        ["hft_backtest/merged_dataset.pyx"],
        language="c++",
        define_macros=define_macros,
    ),
    Extension(
        "hft_backtest.reader", 
        ["hft_backtest/reader.pyx"],
        define_macros=define_macros,
    ),
    Extension(
        "hft_backtest.backtest", 
        ["hft_backtest/backtest.pyx"], 
        language="c++",
        define_macros=define_macros,
    ),
    Extension(
        "hft_backtest.okx.event",
        ["hft_backtest/okx/event.pyx"],
        define_macros=define_macros,
    ),
    Extension(
        "hft_backtest.account",
        ["hft_backtest/account.pyx"],
        define_macros=define_macros,
    ),
    Extension(
        "hft_backtest.okx.account",
        ["hft_backtest/okx/account.pyx"],
        define_macros=define_macros,
    ),
    Extension(
        "hft_backtest.okx.matcher",
        ["hft_backtest/okx/matcher.pyx"],
        define_macros=define_macros,
    ),
    Extension(
        "hft_backtest.okx.reader",
        ["hft_backtest/okx/reader.pyx"],
        define_macros=define_macros,
    ),
    Extension(
        "hft_backtest.okx.benchmark_event",
        ["hft_backtest/okx/benchmark_event.pyx"],
        define_macros=define_macros,
    ),
]

setup(
    name="hft_backtest",
    version="0.1.0",
    description="A high-performance event-driven high-frequency trading backtesting framework.",
    author="Tan yue <1752633783@qq.com>",
    packages=find_packages(),
    install_requires=[
        "numpy",
        "pandas",
        "pyarrow",
        "loguru",
        "Cython",
    ],
    ext_modules=cythonize(
        extensions, 
        compiler_directives=compiler_directives,
    ),
    zip_safe=False,
    include_dirs=[numpy.get_include()],
)