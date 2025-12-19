# 运行时执行以下命令以编译 Cython 模块
# python setup.py build_ext --inplace
# 生成pyi文件 
# stubgen -m hft_backtest.order -o .
# stubgen -m hft_backtest.event -o .

from setuptools import setup, find_packages, Extension
from Cython.Build import cythonize

# 定义扩展模块
extensions = [
    Extension(
        "hft_backtest.event", 
        ["hft_backtest/event.pyx"],
    ),
    Extension(
        "hft_backtest.order",
        ["hft_backtest/order.pyx"],
    ),
    Extension(
        "hft_backtest.event_engine", 
        ["hft_backtest/event_engine.pyx"],
    ),
    Extension(
        "hft_backtest.delaybus", 
        ["hft_backtest/delaybus.pyx"],
        # include_dirs=[numpy.get_include()],
        language="c++",  # <--- 必须有这一行，因为用了 libcpp.vector
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
    ext_modules=cythonize(extensions, compiler_directives={'language_level': "3", 'embedsignature': True, 'binding': True,}),
    zip_safe=False,

    
)