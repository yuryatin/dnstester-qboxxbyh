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

This package is available on PyPI and can be installed with ```pip install dnstester-qboxxbyh ``` or updated with ```pip install --upgrade dnstester-qboxxbyh ```

# How to use

If the DNS proxy filter being tested is a Python script (e.g., mydnsfilter.py): 
```python
from dnstester_qboxxbyh import dnsProxyTester
tester = dnsProxyTester(sample_size_input = 200)
tester.run(app_binary = "python3 mydnsfilter.py", sample_size_input = 200,
                        ignoreUnexpected = False, ignoreTrailing = False,
                        raiseOnTruncation = False, ignoreErrors = False,
                        timeOut = None) # None for timeOut means for ever
```

Or, if the DNS proxy filter being tested is a binary (which may also require its own parameters, such as a configuration file):

```python
from dnstester_qboxxbyh import dnsProxyTester
tester = dnsProxyTester(sample_size_input = 200)
tester.run(app_binary =
  "~/dns-proxy-filter-p2B9agE1/dns_proxy_filter_p2B9agE1 ~/.config/p2B9agE1/dns-proxy-p2B9agE1.conf",
                        sample_size_input = 200, ignoreUnexpected = False, ignoreTrailing = False, cores = 16,
                        raiseOnTruncation = False, ignoreErrors = False,
                        timeOut = None) # None for timeOut means for ever
```

# How it works

The software downloads and uses a collection of 4,170,262 verified domains from https://tranco-list.eu/download/VQ92N/full. It makes a random sample without replacement from this pool of domains and randomly splits it into four subsamples. Using three of those subsamples (one for domains not to be found, one for domains to be refused service, and one for domains with randomly pre-specified IPv4 and IPv6 addresses), the software creates a test configuration file and locally launches the tested DNS proxy filter.

# The test results

The results are displayed and are dynamically updated in the terminal:

<img width="579" height="776" alt="updated_test_results" src="https://github.com/user-attachments/assets/99646274-c56a-433d-abdb-cf13241a3aa3" />


# Constraints

This version doesn't yet support:
* Pre-specifying both IPv4 and IPv6 for the same domain in the configuration file
* Testing the handling of non-standard multi-query DNS requests by a DNS proxy filter
