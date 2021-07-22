import yaml

def parse_protocol(x):

    supported_protocols = ["tcp", "udp"]
    res = x.split("://")
    if len(res) == 2:
        protocol, url = res
    else:
        return None

    if protocol in supported_protocols:
        return (protocol, url)
    
    else:
        raise Exception(f"Protocol {protocol} not supported")

        

def read_config_yaml(path):
    with open(path, "r") as stream:
        config = yaml.load(stream, Loader=yaml.FullLoader)
    return config

