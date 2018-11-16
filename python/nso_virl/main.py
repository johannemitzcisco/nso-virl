# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.application import Service
from ncs.dp import Action
import requests
import lxml.etree as ET
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))+'/../../../nso-py-lib/python')
print sys.path
from nso_py_lib.device import Device

#virl_server_ip = "172.31.21.204"
#username = 'GSVIRL'
#password = 'C1sco123'
#simulation_id = "gti-cores-test-topology-oNiHZX"

class Node():
    

    def __init__(self, id, name, device_type, mgmt_ipv4_address=None, loopback_ipv4_address=None):
        self.id = id
        self.name = name
        self.device_type = device_type
        self.mgmt_ipv4_address = mgmt_ipv4_address
        self.loopback_ipv4_address = loopback_ipv4_address

    def __repr__(self):
        return '{}, {}: {}, {}'.format(self.id, self.name, self.device_type, self.mgmt_ipv4_address)

    def __str__(self):
        return self.__repr__()

class Simulation():
    
    def __init__(self, simulation_id):
        self.id = simulation_id
        self.nodes = []
        self.links = []
        self.simulation_tree = None

    def __repr__(self):
#        return '{}, {}'.format(self.id, '\n'.join(self.nodes))
        return '{}'.format(self.id)

    def __str__(self):
        return self.__repr__()

class VirlServer():

    def __init__(self, log, ip_address, username, password, simengine_port='19399'):
        self.log = log
        self.ip_address = ip_address
        self.auth = (username, password)
        self.virl_server_api = 'http://'+ip_address+':'+simengine_port+'/simengine/rest/'
        self.simulations = {}
        
    def __getSimulationXMLTree(self, simulation):
        request = self.virl_server_api+'export/'+simulation.id+'?updated=true'
        response = requests.get(request, auth=self.auth)
        if response.status_code != 200:
            raise Exception('Error {}: {}'.format(response.status_code, response.text))
        return ET.fromstring(response.content)
    
    def __getSimulationNodes(self, simulation):
        nodes = []
        request = self.virl_server_api+'nodes'+'/'+simulation.id
        response = requests.get(request, auth=self.auth)
        if response.status_code != 200:
            raise Exception('Error {}'.format(response.status_code))
        data = response.json()
        for node_count, node_name in enumerate(data[simulation.id].keys()):
            self.log.info('Found Simulation Node: ', node_name)
            xpath = "/v:topology/v:node[@name='"+node_name+"']/v:extensions/v:entry[@key='AutoNetkit.mgmt_ip']"
            mgmt_ip_address = simulation.simulation_tree.xpath(xpath,namespaces={'v': 'http://www.cisco.com/VIRL'})[0].text
            node = Node(node_count, node_name, data[simulation.id][node_name]['subtype'], mgmt_ip_address)
            nodes.append(node)
        return nodes

    def getSimulations(self):
        request = self.virl_server_api+'list'
        response = requests.get(request, auth=self.auth)
        if response.status_code != 200:
            raise Exception('Error {}'.format(response.status_code))
        data = response.json()
        for simluation_id in data['simulations'].keys():
            simulation = Simulation(simluation_id)
            simulation.simulation_tree = self.__getSimulationXMLTree(simulation)
            simulation.nodes = self.__getSimulationNodes(simulation)
            self.simulations[simluation_id] = simulation
        return self.simulations
        
# ---------------
# ACTIONS EXAMPLE
# ---------------
class LoadVIRLDevices(Action):
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output):
        self.log.info('action name: ', name)
        self.log.info('action input.simulation-id: ', input.simulation_id)

#        for attr in dir(uinfo):
#            self.log.info("obj.%s = %r" % (attr, getattr(uinfo, attr)))
#        output.result = "Test"
#        return

        virl = VirlServer(self.log, input.virl_server_ip_address, input.username, input.password)
        virl.getSimulations()
        try:
            simulation = virl.simulations[input.simulation_id]
        except KeyError as keyerror:
            self.log.info("KeyError: "+str(type(keyerror))+" "+keyerror.message)
            output.result = "Failure"
            return
        self.log.info('Simulation: ', simulation, ' ', simulation.nodes)


        for node in simulation.nodes:
            self.log.info('Registering Node: ', node)
            device = Device(uinfo=uinfo, device_name=node.name, device_type=node.device_type, ip_address=node.mgmt_ipv4_address, port=23, authgroup='virl', log=self.log)
            device.save()


        # Updating the output data structure will result in a response
        # being returned to the caller.
        output.result = "Success"
        self.log.info("Action Complete")



# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS.
# ---------------------------------------------
class Main(ncs.application.Application):
    def setup(self):
        # The application class sets up logging for us. It is accessible
        # through 'self.log' and is a ncs.log.Log instance.
        self.log.info('Main RUNNING')

        self.log.info("System Path:\n"+'\n'.join(sys.path))

        # When using actions, this is how we register them:
        #
        self.register_action('load-virl-sim-devices', LoadVIRLDevices)

        # If we registered any callback(s) above, the Application class
        # took care of creating a daemon (related to the service/action point).

        # When this setup method is finished, all registrations are
        # considered done and the application is 'started'.

    def teardown(self):
        # When the application is finished (which would happen if NCS went
        # down, packages were reloaded or some error occurred) this teardown
        # method will be called.

        self.log.info('Main FINISHED')
