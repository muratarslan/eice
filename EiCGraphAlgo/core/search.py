import time,gc,logging,pickle,os,sys,math
from urllib.parse import urlparse
from core.worker_pool import Worker
from core.pathfinder_async import PathFinder
from core import randompath, graph
from core import config_search

logger = logging.getLogger('pathFinder')
query_log = logging.getLogger('query')

blacklist = config_search.blacklist

class Searcher:
    def __init__(self):
        self.logger = logging.getLogger('pathFinder')
        self.query_log = logging.getLogger('query')
        
    def search(self, start,dest,search_blacklist=blacklist,givenP=None,additionalRes=set(),k = 20,user_context=False,kp=75):
        """Searches a path between two resources start and dest
    
        **Parameters**
        
        start : uri
            resource to start pathfinding
        destination : uri
            destination resource for pathfinding
        search_blacklist : list
            list of resources to exclude in search
        givenP : Pathfinder
            a given pathfinder state for complex search queries
        k : integer
            number of iterations when to break off search
        user_context : uri
            a third resource to compute the score of the path in the context of the third resource.
    
        **Returns**
        
        response : dictionary
            contains execution time, path if found, hash
    
        """
        #print ('starting search')
        #START
        start_time = time.clock()
        
        #Initialization
        if givenP == None:
            p = PathFinder(start,dest)
            p.iterateMatrix(search_blacklist,kp=kp)
        else:
            p = givenP
            p.iterateMatrix(blacklist=search_blacklist,additionalRes=additionalRes,kp=kp)        
        #Iteration 1
        
        paths = p.findPath()
        
        #Following iterations
        while True:
            if not paths == None:
                if len(paths) > 0:
                    break

            self.logger.info ('=== %s-- ===' % str(p.iteration))

            gc.collect()
            m = p.iterateMatrix(blacklist=search_blacklist,kp=kp)
            halt_path = time.clock()
            paths = p.findPath()
            self.logger.info ('Looking for path: %s' % str(time.clock()-halt_path))

            if p.iteration == k:
                break
        resolvedPaths = list()
        
        #FINISH
        if paths:
            for path in paths:
        #       logger.debug(path)
                resolvedPath = graph.resolvePath(path,p.getResources())
                resolvedLinks = graph.resolveLinks(resolvedPath, p.getResourcesByParent())
                formattedPath = list()
                for step in resolvedPath:
                    formattedPath.append(step[1:-1])
                fullPath = dict()
                fullPath['vertices'] = formattedPath
                fullPath['edges'] = resolvedLinks
                resolvedPaths.append(fullPath)
        else:
            return {'path':False,'source':start,'destination':dest,'execution_time':int(round((time.clock()-start_time) * 1000))}
                
        #    graph.visualize(p, path=path)
        finish = int(round((time.clock()-start_time) * 1000))
        r = dict()
        r['execution_time'] = finish
        r['paths'] = resolvedPaths
        r['source'] = start
        r['destination'] = dest
        r['checked_resources'] = p.checked_resources
        r['hash'] = 'h%s' % hash('{0}{1}{2}'.format(start_time,dest,time.time()))
        r['path'] = graph.listPath(resolvedPath,p.getResourcesByParent())
        
        l = 0
        c = 0
        refcount = 0
        usercount = 0
        u = 0
        for step in r['path']:
            if l > 2 and l % 2 == 1:
                c+=1
                m = urlparse(r['path'][l]['uri'])
                m_p = urlparse(r['path'][l-2]['uri'])
                if m.netloc not in r['path'][l-2]['uri']:
                    refcount += 1/2
                refcount += p.jaccard_distance(m.path, m_p.path)/2
            l+=1
            if user_context and l % 2 == 0:
                u += 1
                step = r['path'][l]['uri']
                user_path = self.search(user_context,step,search_blacklist=search_blacklist,givenP=givenP,additionalRes=additionalRes,k = 6)
                if user_path['path']:
                    usercount += 1 / (math.floor(len(user_path['path'])-1)/2)
                else:
                    usercount += 0
        if l > 0:
            r['novelty'] = 0
            if c > 0:    
                r['novelty'] = refcount / c
            if u > 0:
                r['personal_context'] = usercount / u
            
        try:
            path = os.path.dirname(os.path.abspath(__file__))
            file = r['hash']
            file_path = "{0}/stored_paths/{1}.dump".format(path,file)
            f = open(file_path,"wb")
            pickle.dump(r,f)
            f.close()
        except:
            self.logger.warning('could not log and store path between {0} and {1}'.format(start,dest))
            self.logger.error(sys.exc_info())
        self.query_log.info(r)
        self.logger.debug(r)
        result = dict()
        result['path'] = r['path']
        result['hash'] = r['hash']
        result['execution_time'] = r['execution_time']
        result['source'] = r['source']
        result['destination'] = r['destination']
        if 'novelty' in r:
            result['novelty'] = r['novelty']
        if 'personal_context' in r:
            result['user_context'] = r['personal_context']
        return result

class DeepSearcher:
    def __init__(self):
        self.searcher = Searcher()
        
    def searchAllPaths(self, start,dest,search_blacklist=blacklist):
        #START
        start_time = time.clock()
        #RUN
        paths = list()
        prevLenBlacklist = set(search_blacklist)
        path = self.searcher.search(start,dest,prevLenBlacklist)
        new_blacklist = self.generateBlackList(prevLenBlacklist,path)
        paths.append(path)
        while len(new_blacklist) > len (prevLenBlacklist):
            path = self.searcher.search(start,dest,new_blacklist)
            prevLenBlacklist = set(new_blacklist)
            new_blacklist = self.generateBlackList(new_blacklist,path)
            if not path['path'] == False:
                paths.append(path)
        result=dict()
        result['paths']=paths
        result['num_found']=len(paths)
        finish = int(round((time.clock()-start_time) * 1000))
        result['execution_time']=finish
        return result

    def generateBlackList(self, blacklist,response):
        """Expands a given blacklist with a found response"""
        new_blacklist = set(blacklist)
        if not response['path'] == False:
            l = int(len(response['path'])/2)
            for step in response['path'][l-1:l+1]:
                if step['type'] == 'link':
                    #print (step['uri'])
                    new_blacklist.add('<%s>' % step['uri'])
                
        return new_blacklist
    
    def flattenSearchResults(self, response):
        flattened_path = list()
        if not response['path'] == False:
            for step in response['path']:
                if step['type'] == 'node':
                    #print (step['uri'])
                    flattened_path.append('<%s>' % step['uri'])
        return flattened_path
        
    def searchDeep(self, start,dest,search_blacklist=blacklist,k=5,s=3,user_context=False):
        """Searches a path between two resources start and dest
    
        **Parameters**
        
        same as regular search
        
        s: integer
            strength of deepness, how many nodes to trigger for deep search
    
        """
        #START
        start_time = time.clock()
    
        p = PathFinder(start,dest)
        result = self.searcher.search(start,dest,search_blacklist=search_blacklist,givenP=p,k=k,user_context=user_context)
        if not result['path']:
            logger.debug (p.resources)
            deep_roots = p.iterateOptimizedNetwork(s)
            logger.debug (deep_roots)
            print (deep_roots)
            additionalResources = set()
            for st in deep_roots['start']:
                for dt in deep_roots['dest']:
                    logger.debug ("extra path between %s and %s" % (st,dt))
                    print ("extra path between %s and %s" % (st,dt))
                    additionalResources = additionalResources.union(set(self.flattenSearchResults(self.searcher.search(st,dt,k=3*k))))
            result=self.searcher.search(start,dest,search_blacklist=search_blacklist,givenP=p,additionalRes=additionalResources,k = k,user_context=user_context)
        finish = int(round((time.clock()-start_time) * 1000))
        result['execution_time'] = finish
        return result    

class FallbackSearcher:
    def __init__(self, worker=Worker(),searcher=Searcher()):
        self.worker =worker
        self.searcher=searcher
        
    def searchFallback(self,source,destination):
        resp = dict()
        logger.info('Using fallback using random hubs, because no path directly found')
        path_between_hubs = False
        while not path_between_hubs:
            start = time.clock()
            worker_output = dict()
            hubs = randompath.randomSourceAndDestination()
            self.worker.startQueue(self.searchF, 3)
            self.worker.queueFunction(self.searchF,[hubs['source'],hubs['destination'],worker_output,'path_between_hubs'])
            self.worker.queueFunction(self.searchF,[source,hubs['source'],worker_output,'path_to_hub_source'])
            self.worker.queueFunction(self.searchF,[hubs['destination'],destination,worker_output,'path_to_hub_destination'])
            self.worker.waitforFunctionsFinish(self.searchF)
            path_between_hubs = worker_output['path_between_hubs']
            path_to_hub_source = worker_output['path_to_hub_source']
            path_to_hub_destination = worker_output['path_to_hub_destination']
            if path_to_hub_source['path'] == False or path_to_hub_destination['path'] == False:
                path_between_hubs = False
                gc.collect()
                time.sleep(1)
        
        resp['execution_time'] = str(int(round((time.clock()-start) * 1000)))
        resp['source'] = source
        resp['destination'] = destination
        resp['path'] = list()
        resp['path'].extend(path_to_hub_source['path'][:-1])
        resp['path'].extend(path_between_hubs['path'])
        resp['path'].extend(path_to_hub_destination['path'][1:])
        resp['hash'] = False
        return resp
    
    def searchF(self, source, destination, target, index):
        try:
            target[index] = self.searcher.search(source,destination)
        except:
            target[index] = dict()
            target[index]['path'] = False
            logger.error(sys.exc_info())
            logger.error('path between {0} and {1} not found.'.format(source, destination))
             

#r = search(start,dest)
#
#p = r['path']
#time = r['execution_time']
#
#print (str(time)+' ms')
#print (p)
#
#if paths:
#    graph.visualize(p, path=path)
#else:
#    graph.visualize(p)

#print (searchFallback('http://dbpedia.org/resource/Brussels','http://dbpedia.org/resource/Belgium'))
#path = search('http://dbpedia.org/resource/Brussels','http://dbpedia.org/resource/Belgium',blacklist)
#print (len(blacklist))
#print (len(new_blacklist))
#print (new_blacklist)
#path = search('http://dbpedia.org/resource/Brussels','http://dbpedia.org/resource/Belgium',new_blacklist)
##print (len(new_blacklist))


#print (DeepSearcher().searchDeep('http://dbpedia.org/resource/Ireland','http://dbpedia.org/resource/Brussels',blacklist))
#print("search")python profiling like webgrind
#searcher = Searcher()
#print (searcher.search('http://dblp.l3s.de/d2r/resource/authors/Tok_Wang_Ling','http://dblp.l3s.de/d2r/resource/publications/conf/cikm/LiL05a',blacklist))
#print (searcher.search('http://dbpedia.org/resource/Brussels','http://dbpedia.org/resource/Gorillaz',blacklist))
#print (searcher.search('http://dbpedia.org/resource/New_York','http://dbpedia.org/resource/Ireland',blacklist))
#print (searcher.search('http://dbpedia.org/resource/Ohio','http://dbpedia.org/resource/Japan',blacklist))
#print (searcher.search('http://dbpedia.org/resource/Japan','http://dbpedia.org/resource/Tokyo',blacklist))
#print (searcher.search('http://dbpedia.org/resource/Ohio','http://dbpedia.org/resource/Tokyo',blacklist))
#print (searcher.search('http://dbpedia.org/resource/Paris','http://dbpedia.org/resource/Barack_Obama',blacklist))
#print (searcher.search('http://dbpedia.org/resource/Belgium','http://dbpedia.org/resource/Republic_Of_Congo',blacklist))
#print (DeepSearcher().searchAllPaths('http://dbpedia.org/resource/Belgium','http://dbpedia.org/resource/Ireland',blacklist))
#print (searcher.search('http://localhost/selvers','http://localhost/welf',blacklist))

#print (DeepSearcher().searchAllPaths('http://dbpedia.org/resource/Belgium','http://dbpedia.org/resource/Ireland',blacklist))
#print (searcher.search('http://dbpedia.org/resource/Brussels','http://dblp.l3s.de/d2r/resource/authors/Tok_Wang_Ling',blacklist))
#print (DeepSearcher().searchDeep('http://dblp.l3s.de/d2r/resource/authors/Tok_Wang_Ling','http://dbpedia.org/resource/Brussels',blacklist))
#print (searcher.search('http://dblp.l3s.de/d2r/resource/authors/Tok_Wang_Ling','http://dblp.l3s.de/d2r/resource/publications/conf/cikm/LiL05a',blacklist))
#print (search('http://dblp.l3s.de/d2r/resource/authors/Changqing_Li','http://dblp.l3s.de/d2r/resource/authors/Tok_Wang_Ling',blacklist))
    