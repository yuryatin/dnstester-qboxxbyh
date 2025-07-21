import sys
import ipaddress
import socketserver
import socket
import re
import threading
import socketserver
from dnslib import RR, QTYPE, A, AAAA, RCODE, DNSRecord

'''
This is a simple DNS proxy filter prototype.
'''

conf_file_location = '~/.config/p2B9agE1/dns-proxy-p2B9agE1.conf'

class Configuration():
    def __init__(self, config_file=None):        
        self.not_to_find = set()
        self.refuse = set()
        self.a = dict()
        self.aaaa = dict()
        self.ip_listening = ''
        self.port_listening = ''
        self.dns1 = ''
        self.dns2 = ''
        self.dns3 = ''
        self._load_config_file(config_file)

    def _is_valid_hostname(self, domain):
        if len(domain) > 253:
            return False
        labels = domain.rstrip('.').split('.')
        hostname_regex = re.compile(r'^_?[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$')
        return all(hostname_regex.match(label) for label in labels)

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

    def _is_valid_udp_port(self, port_str):
        if not port_str.isdigit():
            return False
        port = int(port_str)
        return 0 <= port <= 65535

    def _load_config_file(self, filepath):
        in_blacklist = False
        in_server = False
        in_upstream = False
        if filepath:
            try:
                with open(filepath) as f:
                    content = [s.strip().lower() for s in f.read().split('\n')]
                    for row in content:
                        if row == '[blacklist]':
                            in_blacklist = True
                            in_server = False
                            in_upstream = False
                        elif row == '[server]':
                            in_server = True
                            in_blacklist = False
                            in_upstream = False
                        elif row == '[upstream]':
                            in_upstream = True
                            in_blacklist = False
                            in_server = False
                        elif row.startswith('[') and row.endswith(']'):
                            in_blacklist = False
                            in_server = False
                            in_upstream = False
                        elif row == '':
                            continue
                        elif in_blacklist:
                            pair = [s.strip() for s in row.split('=')]
                            if len(pair) != 2:
                                continue
                            else:
                                if not self._is_valid_hostname(pair[0]):
                                    continue
                                else:
                                    if pair[1] == 'notfind':
                                        self.not_to_find.add(pair[0])
                                    elif pair[1] == 'refuse':
                                        self.refuse.add(pair[0])
                                    elif self._is_valid_ipv4(pair[1]):
                                        self.a[pair[0]] = pair[1]
                                    elif self._is_valid_ipv6(pair[1]):
                                        self.aaaa[pair[0]] = pair[1]
                        elif in_server:
                            pair = [s.strip() for s in row.split('=')]
                            if len(pair) != 2:
                                continue
                            else:
                                if pair[0] == 'listen_address' and self._is_valid_ipv4(pair[1]):
                                    self.ip_listening = pair[1]
                                elif pair[0] == 'listen_port' and self._is_valid_udp_port(pair[1]):
                                    self.port_listening = pair[1]
                        elif in_upstream:
                            pair = [s.strip() for s in row.split('=')]
                            if len(pair) != 2:
                                continue
                            else:
                                if pair[0] == 'dns1' and self._is_valid_ipv4(pair[1]):
                                    self.dns1 = pair[1]
                                elif pair[0] == 'dns2' and self._is_valid_ipv4(pair[1]):
                                    self.dns2 = pair[1]
                                elif pair[0] == 'dns3' and self._is_valid_ipv4(pair[1]):
                                    self.dns3 = pair[1]
            except FileNotFoundError:
                print(f"Configuration file '{filepath}' not found. Please provide its path as a parameter.")


class CustomUDPServer(socketserver.UDPServer):
    def __init__(self, server_address, RequestHandlerClass, configuration):
        super().__init__(server_address, RequestHandlerClass)
        self.configuration = configuration


class PrototypeDNSProxy(socketserver.BaseRequestHandler):
    def handle(self): #, request, handler):
        confiration = self.server.configuration
        print('HANDLE is CALLED', flush=True)
        data, socket_ = self.request
        request = DNSRecord.parse(data)
        qname = str(request.q.qname).rstrip('.')
        qtype = QTYPE[request.q.qtype]

        reply = request.reply()

        if qname in confiration.refuse:
            reply.header.rcode = RCODE.REFUSED
        elif qname in confiration.not_to_find:
            reply.header.rcode = RCODE.NXDOMAIN
        elif qtype == "A" and qname in confiration.a:
            reply.add_answer(RR(qname, QTYPE.A, rdata=A(confiration.a[qname]), ttl=60))
        elif qtype == "A" and qname in confiration.aaaa:
            reply.header.rcode = RCODE.NOERROR
        elif qtype == "AAAA" and qname in confiration.aaaa:
            reply.add_answer(RR(qname, QTYPE.AAAA, rdata=AAAA(confiration.aaaa[qname]), ttl=60))
        elif qtype == "AAAA" and qname in confiration.a:
            reply.header.rcode = RCODE.NOERROR
        else:
            try:
                forward_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                forward_sock.settimeout(2)
                forward_sock.sendto(data, (confiration.dns1, 53))
                response_data, _ = forward_sock.recvfrom(4096)
                socket_.sendto(response_data, self.client_address)
                return
            except Exception as e:
                print("Upstream error:", e)
                reply.header.rcode = RCODE.SERVFAIL

        socket_.sendto(reply.pack(), self.client_address)


#if __name__ == '__main__':

if len(sys.argv) > 1:
    conf_file_location = sys.argv[1]

config = Configuration(conf_file_location)

server = CustomUDPServer((config.ip_listening, int(config.port_listening)), PrototypeDNSProxy, config)
print(f"DNS proxy running on {config.ip_listening} on UDP port {config.port_listening}...")
threading.Thread(target=server.serve_forever, daemon=True).start()

try:
    while True:
        pass
except KeyboardInterrupt:
    print("\nShutting down.")
    server.shutdown()