# The Python package dnstester-qboxxbyh
This is a tester for a DNS proxy filter. It can be used locally or remotely to test DNS proxy filters that rely on a specific configuration file format below:
```ini
  [server]
  listen_address = 127.0.0.1
  listen_port = 5300
                    
  [upstream]
  dns1 = 1.1.1.1
  dns2 = 8.8.8.8
  dns3 = 8.8.4.4
                    
  [blacklist]
  yandex.ru = notfind
  ya.ru = refuse
  tutu.ru = 178.248.234.61
```

# Installation

This package is available on PyPI and can be installed with ```shell pip install dnstester-qboxxbyh ``` or updated with ```shell pip install --upgrade dnstester-qboxxbyh ```

# How to use

```python
from dnstester_qboxxbyh import dnsProxyTester
tester = dnsProxyTester()
tester.run()
```
