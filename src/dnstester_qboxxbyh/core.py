import requests
import os
import copy
import pickle
from pathlib import Path
import dns.message, dns.rdatatype
import dns.query
import pandas as pd
import sys
import threading
import time
import random
from IPython.display import clear_output
import subprocess
import atexit
import platform
import ipaddress
import logging

logger = logging.getLogger("mylogger")
logger.setLevel(logging.INFO)

if logger.hasHandlers():
    logger.handlers.clear()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler("qboxxbyh.log", mode='w')
file_handler.setFormatter(formatter)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

configFileExample = '''
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
                    '''

class dnsProxyTester():
    def _is_valid_ipv4(self, address):
        try:
            return isinstance(ipaddress.ip_address(address), ipaddress.IPv4Address)
        except ValueError:
            return False
    
    def _is_valid_ipv6(self, address):
        try:
            return isinstance(ipaddress.ip_address(address), ipaddress.IPv6Address)
        except ValueError:
            return False
    
    def __init__(self, ip_input='127.0.0.1', port_input='1053', app_folder='~/.config/p2B9agE1/', sample_size_input = 50, updateResults = True):
        if isinstance(ip_input, str) and (self._is_valid_ipv4(ip_input) or self._is_valid_ipv6(ip_input)):
            self.listen_address = ip_input
        else:
            self.listen_address = '127.0.0.1'
        if isinstance(port_input, str):
            try:
                self.listen_port = str(int(port_input))
            except:
                self.listen_port = '1053'
        elif isinstance(port_input, int):
            self.listen_port = str(port_input)
        else:
            self.listen_port = '1053'
        if isinstance(sample_size_input, int):
            if sample_size_input > 4:
                self.sample_size = sample_size_input
            else:
                self.sample_size = 5
        else:
            self.sample_size = 50
        if isinstance(updateResults, bool):
            self.updateResults = updateResults
        else:
            self.updateResults = True
        self.ignoreUnexpected = False
        self.ignoreTrailing = False
        self.raiseOnTruncation = False
        self.ignoreErrors = False
        self.timeOut = None
        self.lock = threading.Lock()
        self.tranco_list = 'https://tranco-list.eu/download/VQ92N/full'
        self.titles = ('of pass-through sample', 'not to be found', 'to be refused', 'with pre-specified IPs')

        # https://datatracker.ietf.org/doc/html/rfc1035#section-3.2.2
        RFC_1035_chapter_3_2_2_types = ['A', 'NS', 'MD', 'MF', 'CNAME', 'SOA', 'MB', 'MG', 'MR', 'NULL', 'WKS', 'PTR', 'HINFO', 'MINFO', 'MX', 'TXT']
        additional_types = ['PTR', 'NAPTR', 'SRV', 'AAAA']
        self.all_types = [*RFC_1035_chapter_3_2_2_types, *additional_types]
        if isinstance(app_folder, str):
            self.config_file_test_folder = '~/.config/p2B9agE1/'
        self.config_file_name = 'dns-proxy-p2B9agE1.conf'
        self.config_file_template = lambda ip, port, blacklist: f'''
[server]
listen_address = {ip}
listen_port = {port}

[upstream]
dns1 = 1.1.1.1
dns2 = 8.8.8.8
dns3 = 8.8.4.4

[blacklist]
{blacklist}
'''
        self.stop_event = threading.Event()
        domain_test_pool_storage = self.get_or_create_app_data_folder() / "VQ92N_domain_test_pool.pickle"

        if domain_test_pool_storage.is_file():
            with open(domain_test_pool_storage, 'rb') as f:
                self.content = pickle.load(f)
        else:
            print("There is no pool of domains for testing yet. The pool is going to be downloaded from tranco-list.eu", flush=True)
            response = requests.get(self.tranco_list)
            if response.ok:
                print('Download successful')
                self.content = response.content.decode('utf-8').split()
                for i, domain in enumerate(self.content):
                    self.content[i] = domain.split(',')[1]
                with open(domain_test_pool_storage, 'wb') as f:
                    pickle.dump(self.content, f)
                print('Saving of this pool has been finished')

    def get_or_create_app_data_folder(self):
        system = platform.system()
        
        if system == "Darwin":
            base_dir = Path.home() / "Library" / "Application Support"
        elif system == "Linux":
            base_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        elif system == "Windows":
            base_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        else:
            raise OSError(f"Unsupported OS: {system}")
    
        app_data_dir = base_dir / "p2B9agE1"
        app_data_dir.mkdir(parents=True, exist_ok=True)
    
        return app_data_dir

    def update(self, samples):
        counter = 0
        queried_domains_local = [None, None, None, None]
        n_queries_local = [None, None, None, None]
        domains_w_responses = [None, None, None, None]
        queries_w_responses = [None, None, None, None]
        queries_not_found = [None, None, None, None]
        queries_refused = [None, None, None, None]
        proportion_domains = [0.0, 0.0, 0.0, 0.0]
        proportion_queries = [0.0, 0.0, 0.0, 0.0]
        proportion_not_found = [0.0, 0.0, 0.0, 0.0]
        proportion_refused = [0.0, 0.0, 0.0, 0.0]
    
        found_color = ['\033[32m', '\033[31m', '\033[31m', '' ]
        not_found_color = ['', '\033[32m', '', '']
        refused_color = ['', '', '\033[32m', '']
        ip_predefined_color = ['', '', '', '\033[32m']
    
        table_template = lambda i: f"""\n\tQueried\tResponses\t% of queried\t% of all\nDomains\t{queried_domains_local[i]:7d}\t{domains_w_responses[i]:9d}\t{proportion_domains[i]:7.2f}%\t{100.0 * domains_w_responses[i] / self.all_domains[i]:7.2f}%
Queries\t{n_queries_local[i]:7d}\t{found_color[i]}{queries_w_responses[i]:9d}\033[0m\t{proportion_queries[i]:7.2f}%\t{100.0 * queries_w_responses[i] / self.all_types_times_domains[i]:7.2f}%
Not found\t{not_found_color[i]}{queries_not_found[i]:9d}\033[0m\t{proportion_not_found[i]:7.2f}%\t{100.0 * queries_not_found[i] / self.all_types_times_domains[i]:7.2f}
Refused\t\t{refused_color[i]}{queries_refused[i]:9d}\033[0m\t{proportion_refused[i]:7.2f}%\t{100.0 * queries_refused[i] / self.all_types_times_domains[i]:7.2f}%"""
        matching_ips = lambda: f""
    
        while True:
            with self.lock:
                for i in range(4):
                    queried_domains_local[i] = self.queried_domains[i]
                    n_queries_local[i] = self.n_queries[i]
                    filtered_matrix = self.df.loc[self.df.index.isin(samples[i]),]
                    domains_w_responses[i] = filtered_matrix.shape[0]
                    if i == 3:
                        ips_prespecified = filtered_matrix[['A', 'AAAA',  'ipA', 'ipAAAA']].copy()
                    filtered_matrix = filtered_matrix.iloc[:, :20].values
                    queries_w_responses[i] = (filtered_matrix >= 0).sum()
                    queries_not_found[i] = (filtered_matrix == -2).sum()
                    queries_refused[i] = (filtered_matrix == -1).sum()

            if self.updateResults:
                if counter > 0:
                    print("\033[30A", end='')
                try:
                    clear_output(wait=True)
                except:
                    pass
    
            for i in range(4):
                if queried_domains_local[i]:
                    proportion_domains[i] = 100.0 * domains_w_responses[i] / queried_domains_local[i]
                if n_queries_local[i]:
                    proportion_queries[i] = 100.0 * queries_w_responses[i] / n_queries_local[i]
                    proportion_not_found[i] = 100.0 * queries_not_found[i] / n_queries_local[i]
                    proportion_refused[i] = 100.0 * queries_refused[i] / n_queries_local[i]
    
            ip_matched_counter = 0
            ip_queries = (ips_prespecified[['A', 'AAAA']].values > 0).sum()
            
            for i, row in ips_prespecified.iterrows():
                if pd.notna(row['ipA']) and len(row['ipA']) and self.predefinedIP[i][0] == 'IPv4':
                    if row['ipA'][0] == self.predefinedIP[i][1]:
                        ip_matched_counter += 1
                if pd.notna(row['ipAAAA']) and len(row['ipAAAA']) and self.predefinedIP[i][0] == 'IPv6':
                    if row['ipAAAA'][0] == self.predefinedIP[i][1]:
                        ip_matched_counter += 1
                        
            print(f"\r\tProgress\t{self.listen_address}\t{self.listen_port}")
            for i in range(4):
                print(f"\n\t\tDomains {self.titles[i]}" + table_template(i))
                if i == 3:
                    print(f'IPs matched\t{ip_queries}\t{ip_predefined_color[i]}{ip_matched_counter}\033[0m')
            
            sys.stdout.flush()
            counter += 1
            if self.stop_event.is_set():
                break
            time.sleep(0.3)

    def dns_collection(self, domains_list, n):
        domains_queries = set()
        for domain in domains_list:
            with self.lock:
                domains_queries.add(domain)
                self.queried_domains[n] = len(domains_queries)
            for qtype in self.all_types:
                with self.lock:
                    self.n_queries[n] += 1
                q = dns.message.make_query(domain, getattr(dns.rdatatype, qtype))
                try:
                    response = dns.query.udp(q, self.listen_address, port=int(self.listen_port), ignore_unexpected=self.ignoreUnexpected, ignore_trailing = self.ignoreTrailing, raise_on_truncation=self.raiseOnTruncation, ignore_errors=self.ignoreErrors, timeout=self.timeOut)
                except dns.exception.Timeout as e:
                    logger.error(f"{n} : {domain} : {qtype} : DNS Timeout error:")
                    continue
                except dns.query.BadResponse as e:
                    logger.error(f"{n} : {domain} : {qtype} : Bad Response error:")
                    continue
                except dns.message.BadEDNS as e:
                    logger.error(f"{n} : {domain} : {qtype} : Bad EDNS message error:")
                    continue
                except dns.message.BadTSIG as e:
                    logger.error(f"{n} : {domain} : {qtype} : Bad TSIG message error:")
                    continue
                except dns.message.ShortHeader as e:
                    logger.error(f"{n} : {domain} : {qtype} : Short Header message error:")
                    continue
                except dns.message.TrailingJunk as e:
                    logger.error(f"{n} : {domain} : {qtype} : Trailing Junk message error:")
                    continue
                except dns.name.BadLabelType as e:
                    logger.error(f"{n} : {domain} : {qtype} : Bad Label type name error:")
                    continue
                except dns.name.BadPointer as e:
                    logger.error(f"{n} : {domain} : {qtype} : Bad Pointer name error:")
                    continue
                except dns.name.NameTooLong as e:
                    logger.error(f"{n} : {domain} : {qtype} : Name Too Long   error:")
                    continue
                except dns.query.TransferError as e:
                    logger.error(f"{n} : {domain} : {qtype} : Transfer Error query error:")
                    continue
                except dns.query.UnexpectedSource as e:
                    logger.error(f"{n} : {domain} : {qtype} : UnexpectedSource #error:")
                except Exception as e:
                    logger.error(f"{n} {domain} : {qtype} : Unexpected error: {type(e).__name__}")
                    continue
                rcode = response.rcode()
                if rcode == dns.rcode.NXDOMAIN:
                    with self.lock:
                        self.df.loc[domain, qtype] = -2
                elif rcode == dns.rcode.REFUSED:
                    with self.lock:
                        self.df.loc[domain, qtype] = -1
                else:
                    with self.lock:
                        self.df.loc[domain, qtype] = len(response.answer)
                    ips4 = list()
                    ips6 = list()
                    for answer in response.answer:
                        for item in answer.items:
                            if item.rdtype == dns.rdatatype.A:
                                ips4.append(item.address)
                            elif item.rdtype == dns.rdatatype.AAAA:
                                ips6.append(item.address)
                    if ips4:
                        with self.lock:
                            self.df.at[domain, 'ipA'] = tuple(copy.deepcopy(ips4))
                    if ips6:
                        with self.lock:
                            self.df.at[domain, 'ipAAAA'] = tuple(copy.deepcopy(ips6))

    def random_ip(self):
        if random.random() < 0.5:
            return 'IPv4', ".".join(str(random.randint(0, 255)) for _ in range(4))
        else:
            return 'IPv6', ":".join(f"{random.randint(0, 0xFFFF):x}" for _ in range(8))

    def run(self, ip_input = None, port_input = None, app_binary = None, sample_size_input = None, ignoreUnexpected = False, ignoreTrailing = False, raiseOnTruncation = False, ignoreErrors = False, timeOut = None):
        # timeOut = None (in seconds) | waiting forever
        if isinstance(ip_input, str) and (self._is_valid_ipv4(ip_input) or self._is_valid_ipv6(ip_input)):
            self.listen_address = ip_input
        if isinstance(port_input, str):
            try:
                self.listen_port = str(int(port_input))
            except:
                self.listen_port = '1053'
        elif isinstance(port_input, int):
            self.listen_port = str(port_input)
        if isinstance(sample_size_input, int):
            if sample_size_input > 4:
                self.sample_size = sample_size_input
        if isinstance(app_binary, str):
            self.app_binary = app_binary
        else:
            print("Error: you haven't provided as a parameter 'app_binary' for the run() method the binary file path for the DNS proxy filter you want to test. For instance, it can be app_binary='~/p2B9agE1/test_dns' or if your DNS proxy filter is a Python script named test_dns.py, then it can be app_binary='python3 ~/p2B9agE1/test_dns.py'")
            return
        if isinstance(ignoreUnexpected, bool):
            self.ignoreUnexpected = ignoreUnexpected
        if isinstance(ignoreTrailing, bool):
            self.ignoreTrailing = ignoreTrailing
        if isinstance(raiseOnTruncation, bool):
            self.raiseOnTruncation = raiseOnTruncation
        if isinstance(ignoreErrors, bool):
            self.ignoreErrors = ignoreErrors
        if isinstance(timeOut, int) and timeOut > 0:
            self.timeOut = timeOut

        self.df = pd.DataFrame(columns=[*self.all_types, 'ipA', 'ipAAAA'])
        self.queried_domains = [0, 0, 0, 0]
        self.n_queries = [0, 0, 0, 0]

        sampled_domain = random.sample(self.content, min(self.sample_size, len(self.content)))

        quarter_of_sample = len(sampled_domain) // 4
        if quarter_of_sample == 0:
            quarter_of_sample = 1
        n_sampled_domain = len(sampled_domain) - 3 * quarter_of_sample
        not_to_be_found = random.sample(sampled_domain, quarter_of_sample)
        sampled_domain = list(set(sampled_domain) - set(not_to_be_found))
        to_be_refused = random.sample(sampled_domain, quarter_of_sample)
        sampled_domain = list(set(sampled_domain) - set(to_be_refused))
        ips_to_be_substituted = random.sample(sampled_domain, quarter_of_sample)
        sampled_domain = list(set(sampled_domain) - set(ips_to_be_substituted))

        self.predefinedIP = dict()

        blacklist = []
        for domain in not_to_be_found:
            blacklist.append(f'{domain} = notfind')
        for domain in to_be_refused:
            blacklist.append(f'{domain} = refuse')
        for domain in ips_to_be_substituted:
            new_ip = self.random_ip()
            self.predefinedIP[domain] = new_ip
            blacklist.append(f'{domain} = {new_ip[1]}')

        random.shuffle(blacklist)

        config_path = os.path.expanduser(self.config_file_test_folder)
        os.makedirs(config_path, exist_ok=True)
        with open(config_path + self.config_file_name, 'w') as f:
            f.write(self.config_file_template(self.listen_address, self.listen_port, '\n'.join(blacklist)))
        
        self.all_domains = (len(sampled_domain), quarter_of_sample, quarter_of_sample, quarter_of_sample)
        self.all_types_times_domains = (len(sampled_domain) * len(self.all_types), quarter_of_sample * len(self.all_types), quarter_of_sample * len(self.all_types), quarter_of_sample * len(self.all_types))
        
        time.sleep(1)
        
        if self.listen_address == '127.0.0.1' or self.listen_address == '::1':
            try:
                proc = subprocess.Popen(
                    [*[os.path.expanduser(part) for part in self.app_binary.split()]], #, config_path + self.config_file_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            except FileNotFoundError as e:
                print(f"Error: the specified binary file '{self.app_binary}' does not seem to exist or there is another error {e}. Please check the path and try again.")
                return
            except Exception as e:
                print(f"An unexpected error occurred while starting the DNS proxy filter for testing: {e}")
                return

        time.sleep(2)
        
        print_update = threading.Thread(target=self.update, args=((sampled_domain, not_to_be_found, to_be_refused, ips_to_be_substituted),))
        print_update.start()
        
        threads = []
        
        for i, sample in enumerate((sampled_domain, not_to_be_found, to_be_refused, ips_to_be_substituted)):
            t = threading.Thread(target=self.dns_collection, args=(sample, i))
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        self.stop_event.set()
        print_update.join()

        for i, sample in enumerate((sampled_domain, not_to_be_found, to_be_refused, ips_to_be_substituted)):
            filtered_matrix = self.df.loc[self.df.index.isin(sample),]
            filtered_matrix = filtered_matrix.iloc[:, :20]
            if (filtered_matrix.values == -2).sum():
                domains_not_found = filtered_matrix[filtered_matrix.eq(-2).any(axis=1)].index.tolist()
                print(f"\nThe following domains {self.titles[i]} were not found for at least one type of query:\n\t{' '.join(domains_not_found)}")
        
        for i, sample in enumerate((sampled_domain, not_to_be_found, to_be_refused, ips_to_be_substituted)):
            filtered_matrix = self.df.loc[self.df.index.isin(sample),]
            filtered_matrix = filtered_matrix.iloc[:, :20]
            if (filtered_matrix.values == -1).sum():
                domains_refused = filtered_matrix[filtered_matrix.eq(-1).any(axis=1)].index.tolist()
                print(f"\nThe following domains {self.titles[i]} were among those for which at least one type of query was refused:\n\t{' '.join(domains_refused)}")
        
        print('\nTEST FINISHED')
        
        if proc.poll() is None:
            atexit.register(proc.terminate)

        time.sleep(3)

        if proc.poll() is None:
            proc.kill()