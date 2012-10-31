'''
Created on 13-sep.-2012

@author: ldevocht
'''
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import sys
from itertools import islice, chain
import logging

logger = logging.getLogger('pathFinder')

def resolvePath(path,resources):
    resolvedPath = list()
    for step in path:
        resolvedPath.append(resources[step])
    return resolvedPath

def batch(iterable, size):
    sourceiter = iter(iterable)
    while True:
        batchiter = islice(sourceiter, size)
        yield chain([next(batchiter)], batchiter)

def rolling_window(seq, window_size):
    it = iter(seq)
    win = [next(it) for cnt in range(window_size)] # First window
    yield win
    for e in it: # Subsequent windows
        win[:-1] = win[1:]
        win[-1] = e
        yield win
        
def resolveLinks(resolvedPath,resourcesByParent):
    resolvedLinks = list()
    for iterator in rolling_window(resolvedPath, 2):
        steps = list(iterator)
        #logger.debug (steps)
        if len(steps) == 2:
            resolvedLinks.append((resourcesByParent[steps[0]][steps[1]])['uri'][1:-1])
    return resolvedLinks
                                                   
def listPath(resolvedPath,resourcesByParent):
    resolvedEdges = list()
    listedPath = list()
    for iterator in rolling_window(resolvedPath, 2):
        steps = list(iterator)
        #logger.debug (steps)
        if len(steps) == 2:
            resolvedEdges.append(resourcesByParent[steps[0]][steps[1]])
            
    for node in resolvedPath:
        step = dict()
        step['uri'] = node.strip('<>')
        step['type'] = 'node'
        listedPath.append(step)
        if len(resolvedEdges) > 0:
            step = dict()
            step['uri'] = resolvedEdges[0]['uri'].strip('<>')
            step['type'] = 'link'
            step['inverse'] = resolvedEdges[0]['inverse']
            listedPath.append(step)
            del resolvedEdges[0]
    return listedPath

def pathExists(M):
    G = nx.Graph(M)
    return nx.has_path(G, 0, 1)

def path(pathFinder):
    G = buildWeightedGraph(pathFinder)
    try:
        if nx.has_path(G, 0, 1):
            logger.info ('Looking for path')
            return [nx.astar_path(G,0,1,pathFinder.jaccard,weight='weight')]
            #return list(nx.all_simple_paths(G,0,1,cutoff=8))
        else:
            return None
        
    except:
        logger.error (sys.exc_info())
        return None
    
def buildWeightedGraph(pathFinder):
    M=pathFinder.getGraph()
    G = nx.Graph(M)
    for i in range(len(M)-1):
        for j in range(len(M[i])-1):
            if M[i][j] == 1:
                G[i][j]['weight'] = np.log(deg(i,pathFinder)+deg(j,pathFinder))
    return G

def deg(node,pathFinder):
    resources = pathFinder.getResources()
    resourcesByParent = pathFinder.getResourcesByParent()
    return len(resourcesByParent[resources[node]])
    
def visualize(pathFinder, path=None):
    M = pathFinder.getGraph()
    resources = pathFinder.getResources()
    resourcesByParent = pathFinder.getResourcesByParent()
    G = buildWeightedGraph(pathFinder)
    pos=nx.spring_layout(G)
    offset = -0.02
    pos_labels = {}
    keys = pos.keys()
    for key in keys:
        x, y = pos[key]
        pos_labels[key] = (x, y+offset)
    grandmother=[0]
    grandfather=[1]
    children=[]
    grandchildren=[]
    for i in range(len(M)):
            if i==0 or i==1:
                pass
            elif i not in children:
                if np.sum(M[i]) > 2.1:
                    children.append(i)
                else:
                    grandchildren.append(i)
                    
    labels=dict()
    labels[0]=resources[0]
    labels[1]=resources[1]

    nx.draw_networkx_edges(G,pos,alpha=0.25)
    nx.draw_networkx_nodes(G, pos, node_size=300, nodelist=grandmother, node_color='g')
    nx.draw_networkx_nodes(G, pos, node_size=300, nodelist=grandfather, node_color='r')
    nx.draw_networkx_nodes(G, pos, node_size=150, nodelist=children, node_color='white')
    nx.draw_networkx_nodes(G, pos, node_size=50, nodelist=grandchildren, node_color='grey')
    pathlinks=list()
    edge_labels=dict()
    if path:
        for iterator in rolling_window(path, 2):
            steps = list(iterator)
            link = (steps[0],steps[1])
            pathlinks.append(link)
            # logger.debug (link)
            label = resourcesByParent[resources[steps[0]]][resources[steps[1]]]
            label = label.strip('<>')
            splitted = label.split("/")
            final_label = ':'+splitted[len(splitted)-1]
            edge_labels[link] = final_label
            
        for node in path:
            if node >= 2:
                labels[node] = resources[node]
        nx.draw_networkx_edges(G,pos,edgelist=pathlinks,width=2.0,alpha=0.35,edge_color='b')
    
    nx.draw_networkx_labels(G,pos_labels,labels,font_size=10)
    nx.draw_networkx_edge_labels(G,pos,edge_labels=edge_labels,font_size=10)
    
    #logger.debug(G.nodes)
    plt.axis('off')
    plt.show(G)