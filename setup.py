# 运行时执行以下命令以编译 Cython 模块
# python setup.py build_ext --inplace

from setuptools import setup, find_packages, Extension
from Cython.Build import cythonize


extensions = [
    Extension("hft_backtest.event", ["hft_backtest/event.pyx"]),
    Extension("hft_backtest.order", ["hft_backtest/order.pyx"]),
    #Extension("hft_backtest.okx.event", ["hft_backtest/okx/event.pyx"]),
]

setup(
    name="hft_backtest",  # 包名（唯一标识）
    version="0.1",
    packages=find_packages(),  # 自动发现包目录
    install_requires=[],       # 依赖列表（可选）
    ext_modules=cythonize(extensions, language_level=3),
)