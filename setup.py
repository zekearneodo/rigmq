from setuptools import setup

setup(name='rigmq',
      version='0.1',
      description='Rig controller with single board computer/monitor pc and other devices via zmq',
      url='http://github.com/zekearneodo/sbcrig',
      author='Zeke Arneodo',
      author_email='ezequiel@ini.ethz.ch',
      license='MIT',
      packages=['rigmq'],
      install_requires=['numpy',
                        'h5py',
                        'pyzmq'],
      zip_safe=False)
