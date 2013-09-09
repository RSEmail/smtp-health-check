
from setuptools import setup, find_packages


setup(name='smtp-health-check',
      version='0.1.0',
      author='Ian Good',
      author_email='ian.good@rackspace.com',
      description='Initiates an SMTP connection to a host and determines its health based on status codes and timers.',
      url='https://github.com/icgood/smtp-health-check',
      packages=find_packages(),
      install_requires=[],
      entry_points={'console_scripts': ['smtp-health-check = smtphealth.main:main']},
      classifiers=['Development Status :: 3 - Alpha',
                   'Programming Language :: Python'])


# vim:et:fdm=marker:sts=4:sw=4:ts=4
