import unittest
import md5
import requests
from scrapy.selector import Selector
import json
import os
import random
import string
import datetime

from gourmet.plugins.import_export.scrapy_import_plugin.essenUndTrinken_plugin import EssenUndTrinkenPlugin
from gourmet.plugins.import_export.scrapy_import_plugin.brigitte_plugin import BrigittePlugin

class FileScrambleWrapped(object):
    def __init__(self, file_):
        self._file = file_
        
        random.seed(a="XYZ")
        ls = list(string.ascii_lowercase+string.ascii_uppercase+"0123456789\\/(). :{}[]\"")
        lsOrig = list(ls)
        random.shuffle( ls )
        
        self.scramble = dict( zip( lsOrig, ls ) )
        self.unscramble = dict( zip( ls, lsOrig ) )

    def write(self, data):
        o = []
        for c in data:
            if c in self.scramble:
                c = self.scramble[c]
            o.append(c)
        return self._file.write("".join(o))
    
    def read(self):
        data = self._file.read()
        o = []
        for c in data:
            if c in self.unscramble:
                c = self.unscramble[c]
            o.append(c)
        return "".join(o)
    
    def __exit__(self,*args):
        return self._file.__exit__(*args)

    def __enter__(self):
        self._file.__enter__()
        return self

    def __getattr__(self, attr):
        return getattr(self._file, attr)

class TestScrapyImportersMeta(type):
    def __new__(cls, name, bases, attrs):
        description = []
        description.append(
            {
                "plugin": EssenUndTrinkenPlugin,
                "urls": [
                      # This url has multiple ingredient groups
                      "http://www.essen-und-trinken.de/rezept/116692/doradenfilets-mit-tomaten-kartoffelpueree.html",
                      # Here no ingredient groups
                      "http://www.essen-und-trinken.de/rezept/3297/tomaten-kartoffeln.html"
                      ]
            }
           )  
              
        description.append(
            {
                "plugin": BrigittePlugin,
                "urls":[
                      # This url has multiple ingredient groups
                      "http://www.brigitte.de/rezepte/marinierter-lachs-mit-limetten-aioli-10554098.html",
                      # Here no ingredient groups
                      "http://www.brigitte.de/rezepte/roestkartoffeln-10554078.html",
                      ]
            }
           )        

        
        for x in description:
            counter = 0
            for url in x["urls"]:
                methodName = "test_{0}_{1:02}".format( x["plugin"].internalName, counter )
                attrs[methodName] = cls._createTestCase(x["plugin"], url)
                counter += 1

        return super(TestScrapyImportersMeta, cls).__new__(cls, name, bases, attrs)

    @classmethod
    def _createTestCase(cls, plugin, url):
        def _testCase(self):
            pluginInstance = plugin()
            self._testPlugin(url, pluginInstance)
        return _testCase 
    
class TestScrapyImporters(unittest.TestCase):
    __metaclass__ = TestScrapyImportersMeta
 
    def _downloadItem(self, url, urlHash):
        maxCacheTime = datetime.timedelta(days=7)
        testWebsiteCacheDir = os.path.join( os.path.dirname(os.path.realpath(__file__)), 'testWebsiteCache' )
        cacheFileName = os.path.join(testWebsiteCacheDir,urlHash+".html")
        metaFileName = os.path.join(testWebsiteCacheDir,urlHash+".meta")
        
        now = datetime.datetime.utcnow()
        content = None
        
        try:
            with open(metaFileName) as infile:
                timeCache = datetime.datetime.strptime(infile.readline(), "%Y-%m-%d %H:%M:%S.%f")
            if now <= timeCache + maxCacheTime and timeCache <= now:
                with open(cacheFileName) as infile:
                    content = infile.read()
        except IOError:
            pass
        
        if not content:
            r = requests.get(url)
            self.assertEqual(r.status_code, 200, "Problem downloading page")
            with open(cacheFileName, 'w') as outfile:
                outfile.write(r.content)
            with open(metaFileName, 'w') as outfile:
                outfile.write( str(now) )
            content = r.content
            
        return content
    
    def _testPlugin(self, url, plugin):
        """ This is a generic testing method which will load the url from
        remote and pass it to the parser. Finally the received recipe structure
        will be compared against reference data inside testData.
        """
        urlHash = md5.new(url).hexdigest()
        # print("Testing Url: %s hash: %s" %(url,urlHash) )
                
        data = self._downloadItem( url, urlHash )
        
        self.assertGreaterEqual(plugin.test_url( url, data ), 1 )

        parser = plugin.get_parser()
        recipe = parser.parse( Selector(text=data) )

        # Load test data ...
        testOk = True
        testDataDir = os.path.join( os.path.dirname(os.path.realpath(__file__)), 'testData' )
        refFileName = os.path.join(testDataDir,urlHash+".json")
        try:
            with FileScrambleWrapped( open(refFileName) ) as infile:    
                recipeReference = json.load(infile)

            if recipe != recipeReference:
                print("parsed recipe and reference differs")
                with open(refFileName+".ref.readable", 'w') as outfile:
                    with FileScrambleWrapped( open(refFileName) ) as infile:    
                        outfile.write(infile.read())
                testOk = False
        except IOError:
            print("No reference found.")
            testOk = False

        if not testOk:
            storeFileName = refFileName + ".loaded.readable"
            storeScrambledFileName = refFileName + ".loaded"
            print("Reference saved to %s; check it for validity" % storeFileName)
            print("Move file %s to %s for creating a golden sample." % (storeScrambledFileName, refFileName))
            with FileScrambleWrapped( open(storeScrambledFileName, 'w') ) as outfile:
                json.dump(recipe, outfile, sort_keys=True,
                          indent=4, separators=(',', ': '))
            with open(storeFileName, 'w') as outfile:
                json.dump(recipe, outfile, sort_keys=True,
                          indent=4, separators=(',', ': '))
            
        self.assert_(testOk, "Failed to get reference data or data is not equal for url: %s hash: %s"%(url, urlHash))    

if __name__ == '__main__':
    unittest.main()
    # Run script from gourmet top directory with:
    # export PYTHONPATH="$(pwd)";  python gourmet/plugins/import_export/scrapy_import_plugin/test_scrapy_import_plugin.py
    