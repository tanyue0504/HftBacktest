# 运行时执行以下命令以编译 Cython 模块
# python setup.py build_ext --inplace

from setuptools import setup, find_packages, Extension
from Cython.Build import cythonize
import numpy

# 定义扩展模块
extensions = [
    Extension(
        "hft_backtest.event", 
        ["hft_backtest/event.pyx"],
        include_dirs=[numpy.get_include()] # 如果未来event涉及numpy交互
    ),
    # Extension(
    #     "hft_backtest.order", 
    #     ["hft_backtest/order.pyx"],
    #     include_dirs=[numpy.get_include()]
    # ),
    # 如果需要编译 okx 下的 event，取消注释
    # Extension("hft_backtest.okx.event", ["hft_backtest/okx/event.pyx"]),
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
    ext_modules=cythonize(extensions, compiler_directives={'language_level': "3"}),
    zip_safe=False,
)