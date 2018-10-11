import threading
import time
import yaml


from kubernetes import client, config, watch

# Following line is sourcing your ~/.kube/config so you are authenticated same
# way as kubectl is
config.load_kube_config()
v1 = client.CoreV1Api()
crds = client.CustomObjectsApi()
gordon_api_version = 'v1'
gordon_name = 'gordons'

crd_group = "operator.prgcont.cz" # group of crd to be vatched
contexts, active_context = config.list_kube_config_contexts()
if not contexts:
    print("Cannot find any context in kube-config file.")

namespace = config.list_kube_config_contexts()[1]["context"]["namespace"]
print('Using autodetected namespace: {}').format(namespace)

pod_template = yaml.safe_load("""
apiVersion: v1
kind: Pod
metadata:
  generateName: gordon-
spec:
  containers:
    - name: gordon
      image: prgcont/gordon:v1.0
""")


def main():
    # our simple watch loop for changes in our crd
    stream = watch.Watch().stream(crds.list_namespaced_custom_object,
                                  crd_group,
                                  gordon_api_version,
                                  namespace,
                                  gordon_name)
    for event in stream:
        if event['type'] == 'ADDED':
            print ("I am deploying pods")
            deploy(event['object'])
        elif event['type'] == 'MODIFIED':
            print ("I am modifying pods")
            change(event['object'])
        elif event['type'] == 'DELETED':
            print ("I am deleting pods")
            delete(event['object'])
        else:
            print('Unsupported change type: %s' % event['type'])


def deploy(crd):
    replicas = crd['spec']['gordon']['replicas']
    name = crd['metadata']['name']
    if 'state' in crd:
        print('[%s] Already exists!' % name)
        return
    else:
        crd['state'] = {}
        crd['state']['pods'] = []
    print('[%s] Deploying %s replicas of gordon.' %
          (name,
           replicas))
    i = 1
    while i <= replicas:
        resp = v1.create_namespaced_pod(namespace, pod_template)
        crd['state']['pods'].append(resp.metadata.name)
        print('[%s] Scheduled pod %s' % (name,
                                         resp.metadata.name))
        i += 1

    crd['state']['replicas'] = replicas
    crds.patch_namespaced_custom_object(crd_group,
                                        gordon_api_version,
                                        namespace,
                                        gordon_name,
                                        name,
                                        crd)


def change(crd):
    replicas = crd['spec']['gordon']['replicas']
    name = crd['metadata']['name']
    print('[%s] Modifying.' % name)
    i = crd['state']['replicas']
    if i > replicas:
        while i > replicas:
            pod = crd['state']['pods'].pop()
            print('[%s] Removing pod %s .' % (name, pod))
            v1.delete_namespaced_pod(pod,
                                     namespace,
                                     client.V1DeleteOptions())
            i -= 1
    elif i < replicas:
        while i <= replicas:
            resp = v1.create_namespaced_pod(namespace, pod_template)
            crd['state']['pods'].append(resp.metadata.name)
            print('[%s] Scheduled pod %s' % (name,
                                             resp.metadata.name))
            i += 1
    crd['state']['replicas'] = i
    crds.patch_namespaced_custom_object(crd_group,
                                        gordon_api_version,
                                        namespace,
                                        gordon_name,
                                        name,
                                        crd)


def delete(crd):
    
    
    print ("You've decided to delete the entire cluster..")
    replicas = crd['spec']['gordon']['replicas']
    while replicas!=0:
        print ("Deleting the replica pods..")
        pod = crd['state']['pods'].pop()
        v1.delete_namespaced_pod(pod,
                                 namespace,
                                 client.V1DeleteOptions())
        replicas -=1
    print ("All replicas are deleted")  





class Checker(threading.Thread):

    def run(self):
        while True:
            time.sleep(1)


if __name__ == "__main__":
    checker = Checker()
    checker.daemon = True
    checker.start()
    main()