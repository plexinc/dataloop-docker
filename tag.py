import logging
import grequests
import sys
import getopt
import time
import dl_lib

logger = logging.getLogger(__name__)


def tag(ctx):
    while True:
        logger.debug("tagging")
        try:
            containers = dl_lib.get_containers(ctx)
            container_paths = dl_lib.get_container_paths(containers)
            tag_containers(ctx, container_paths)
        except Exception as ex:
            logger.error("tagging failed: %s" % ex, exc_info=True)
        finally:
            time.sleep(ctx['tag_interval'])


def tag_containers(ctx, container_paths):

    api_host = ctx['api_host']
    headers = dl_lib.get_request_headers(ctx)

    def create_request(path):
        tags = get_tags(ctx, path)
        data = {'names': ','.join(tags)}

        finger = dl_lib.hash_id(path)
        url = "%s/api/agents/%s/tags" % (api_host, finger,)
        return grequests.put(url, json=data, headers=headers)

    reqs = map(create_request, container_paths)
    grequests.map(reqs)


def get_tags(ctx, container_path):
    container = dl_lib.get_container(ctx, container_path)

    tags = ["all", "docker"]
    tags += container_aliases(container)
    tags += container_image(container)
    tags += contain_env_vars(container)
    tags += container_host_name()

    return tags


def container_aliases(container):
    def not_name(alias):
        return alias not in container['name']

    return filter(not_name, container['aliases'])


def container_image(container):
    return [dl_lib.slugify(container['spec']['image'])]


def contain_env_vars(container):
    id = dl_lib.get_container_id(container['name'])
    env_vars = dl_lib.get_container_env_vars(id)
    env_vars_to_tag = ['ENV', 'APP_NAME']
    env_var_tags = []
    for var in env_vars_to_tag:
        if var in env_vars:
            env_var_tags += [env_vars[var]]

    return env_var_tags


def container_host_name():
    return [dl_lib.container_real_host_name()]


def main(argv):
    ctx = {
        "tag_interval": 10,
        "api_host": "https://www.dataloop.io",
        "cadvisor_host": "http://127.0.0.1:8080"
    }

    try:
        opts, args = getopt.getopt(argv, "ha:c:u::", ["apikey=", "cadvisor=", "apiurl="])
    except getopt.GetoptError:
        print 'tag.py -a <apikey> -c <cadvisor address:port> -u <dataloop api address:port>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'tag.py -a <apikey> -c <cadvisor address:port> -u <dataloop address:port>'
            sys.exit()
        elif opt in ("-a", "--apikey"):
            ctx['api_key'] = arg
        elif opt in ("-c", "--cadvisor"):
            ctx['cadvisor_host'] = arg
        elif opt in ("-u", "--apiurl"):
            ctx['api_host'] = arg


    while True:
        tag(ctx)
        time.sleep(ctx['tag_interval'])


if __name__ == "__main__":
    main(sys.argv[1:])
