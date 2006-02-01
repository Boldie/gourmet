import re, string
import sys
from parser_data import SUMMABLE_FIELDS

# Our basic module for interaction with our nutritional information DB

class NutritionData:

    """Handle all interactions with our nutrition database.

    We provide methods to set up equivalences between our
    ingredient-keys and our nutritional data.
    """
    
    def __init__ (self, db, conv):
        self.db = db
        self.conv = conv
        self.conv.density_table
        self.gramwght_regexp = re.compile("([0-9.]+)?( ?([^,]+))?(, (.*))?")
        self.wght_breaker = re.compile('([^ ,]+)([, ]+\(?(.*)\)?)?$')

    def set_key (self, key, row):
        """Create an automatic equivalence for ingredient key 'key' and nutritional DB row ROW
        """        
        if not row: row = self._get_key(key)
        #density=self.get_density(key,row)
        if row: self.row.ndbno=row.ndbno
        else:
            self.db.do_add(self.db.naliasesview,
                           {'ndbno':row.ndbno,
                            'ingkey':key})

    def set_density_for_key (self, key, density_equivalent):
        self.db.update(
            self.db.naliasesview,
            {'ingkey':key},
            {'density_equivalent':density_equivalent}
            )

    def set_key_from_ndbno (self, key, ndbno):
        """Create an automatic equivalence between ingredient key 'key' and ndbno
        ndbno is our nutritional database number."""
        if type(ndbno)!=int:
            ndbno = int(ndbno)
        self.db.do_add(self.db.naliasesview,{'ndbno':ndbno,
                                             'ingkey':key}
                       )

    def set_conversion (self, key, unit, factor):
        """Set conversion for ingredient key.

        factor is the amount we multiply by to get from unit to grams.
        """
        if self.conv.unit_dict.has_key(unit):
            unit = self.conv.unit_dict[unit]
        self.db.do_add(self.db.nconversions,{'ingkey':key,'unit':unit,'factor':factor})

    def get_matches (self, key, max=50):
        """Handed a string, get a list of likely USDA database matches.

        We return a list of lists:
        [[description, nutritional-database-number],...]

        If max is not none, we cut our list off at max items (and hope our
        sorting algorithm succeeded in picking out the good matches!).
        """
        words=re.split("\W",key)
        words = filter(lambda w: w and not w in ['in','or','and','with'], words)
        #words += ['raw']
        result =  self.db.search_nutrition(words)
        while not result and len(words)>1:
            words = words[:-1]
            result = self.db.search_nutrition(words)
        if result:
            return [(r.desc,r.ndbno) for r in result]
        else:
            return None
            
    def _get_key (self, key):
        """Handed an ingredient key, get our nutritional Database equivalent
        if one exists."""
        row=self.db.fetch_one(self.db.naliasesview,**{'ingkey':str(key)})
        return row

    def get_nutinfo_for_ing (self, ing):
        """A convenience function that grabs the requisite items from
        an ingredient."""
        if hasattr(ing,'rangeamount') and ing.rangeamount:
            # just average our amounts
            amount = (ing.rangeamount + ing.amount)/2
        else:
            amount = ing.amount
        if not amount: amount=1
        return self.get_nutinfo_for_item(ing.ingkey,amount,ing.unit)

    def get_nutinfo_for_inglist (self, inglist):
        """A convenience function to get NutritionInfoList for a list of
        ingredients.
        """
        return NutritionInfoList([self.get_nutinfo_for_ing(i) for i in inglist])

    def get_nutinfo_for_item (self, key, amt, unit):
        """Handed a key, amount and unit, get out nutritional Database object.
        """
        ni=self.get_nutinfo(key)        
        if ni:
            c=self.get_conversion_for_amt(amt,unit,key)
            if c:
                return NutritionInfo(ni,mult=c)
        return NutritionVapor(self,key,
                              rowref=ni,
                              amount=amt,
                              unit=unit)

    def get_nutinfo (self, key):
        """Get our nutritional information for ingredient key 'key'
        We return an object interfacing with our DB whose attributes
        will be nutritional values.
        """
        aliasrow = self._get_key(key)
        if aliasrow:
            nvrow=self.db.fetch_one(self.db.nview,**{'ndbno':aliasrow.ndbno})
            if nvrow: return NutritionInfo(nvrow)
        # if we don't have a nutritional db row, return a
        # NutritionVapor instance which remembers our query and allows
        # us to redo it.  The idea here is that our callers will get
        # an object that can guarantee them the latest nutritional
        # information for a given item.
        return NutritionVapor(self,key)

    def get_ndbno (self, key):
        aliasrow = self._get_key(key)
        if aliasrow: return aliasrow.ndbno
        else: return None

    def convert_to_grams (self, amt, unit, key, row=None):
        conv = self.get_conversion_for_amt(amt,unit,key,row)
        if conv: return conv*100
        else:
            return None

    def get_conversion_for_amt (self, amt, unit, key, row=None, fudge=True):
        """Get a conversion for amount amt of unit 'unit' to USDA standard.

        Multiplying our standard numbers (/100g) will get us the appropriate
        calories, etc.

        get_conversion_for_amt(amt,unit,key) * 100 will give us the
        number of grams this AMOUNT converts to.
        """
        # our default is 100g
        cnv=self.conv.converter('g.',unit)
        if not row: row=self.get_nutinfo(key)
        if not cnv:
            cnv = self.conv.converter('g.',unit,
                                      density=self.get_density(key,row,fudge=fudge)
                                      )
        if not cnv:
            # Check our weights tables...
            extra_conversions = self.get_conversions(key,row)[1]
            if extra_conversions.has_key(unit):
                cnv = extra_conversions[unit]
            elif extra_conversions.has_key(unit.lower()):
                cnv = extra_conversions[unit.lower()]
        if not cnv:
            # lookup in our custom nutrition-related conversion table
            if self.conv.unit_dict.has_key(unit):
                unit = self.conv.unit_dict[unit]
            lookup = self.db.fetch_one(self.db.nconversions,ingkey=key,unit=unit)
            if lookup:
                cnv = lookup.factor
            else:
                # otherwise, cycle through any units we have and see
                # if we can get a conversion via those units...
                for conv in self.db.fetch_all(self.db.nconversions,ingkey=key):
                    factor = self.conv.converter(unit,conv.unit)
                    if factor:
                        cnv = conv.factor*factor
        if cnv:
            return (0.01*amt)/cnv

    def get_conversions (self, key=None, row=None):
        """Handed an ingredient key or a row of the nutrition database,
        we return two dictionaries, one with Unit Conversions and the other
        with densities. Our return dictionaries look like this:
        ({'chopped':1.03, #density dic
          'melted':1.09},
         {'piece':27,
          'leg':48,} # unit : grams
          )"""
        if not row: row=self.get_nutinfo(key)
        if not row: return {},{}
        units = {}
        densities = {}
        for gd,gw in self.get_gramweights(row).items():
            a,u,e=gd
            if a:
                convfactor = self.conv.converter(u,'ml')
                if convfactor: #if we are a volume
                    # divide mass by volume converted to mililiters
                    # (since gramwts are in grams!)
                    density = float(gw) / (a * convfactor)
                    densities[e]=density
                    continue
            # if we can't get a density from this amount, we're going to treat it as a unit!
            if e: u = u + ", " + e
            if a: gw = float(gw)/a
            else:
                gw = float(gw)
            if u: units[u]=gw
        return densities,units
            
    def get_densities (self,key=None,row=None):
        """Handed key or nutrow, return dictionary with densities."""
        if not row: row = self._get_key(key)
        if not row: return None
        if self.conv.density_table.has_key(key):
            return {'':self.conv.density_table[key]}
        else:
            densities = {}       
            for gd,gw in self.get_gramweights(row).items():
                a,u,e = gd
                if not a:
                    continue
                convfactor=self.conv.converter(u,'ml')
                if convfactor: # if we are a volume
                    # divide mass by volume converted to milileters
                    # (gramwts are in grams)
                    density = float(gw) / (a * convfactor)
                    densities[e]=density
            return densities

    def get_gramweights (self,row):
        """Return a dictionary with gram weights.
        """
        ret = {}
        nutweights = self.db.fetch_all(self.db.nwview,**{'ndbno':row.ndbno})
        for nw in nutweights:
            mtch = self.wght_breaker.match(nw.unit)
            if not mtch:
                unit = nw.unit
                extra = None
            else:
                unit = mtch.groups()[0]
                extra = mtch.groups()[2]
            ret[(nw.amount,unit,extra)]=nw.gramwt
        return ret
    
    def get_density (self,key=None,row=None, fudge=True):
        densities = self.get_densities(key,row)
        if densities.has_key(''): densities[None]=densities['']
        if key: keyrow=self._get_key(key)        
        if densities:
            if key and keyrow.density_equivalent and densities.has_key(keyrow.density_equivalent):
                return densities[keyrow.density_equivalent]
            elif densities.has_key(None):
                self.conv.density_table[key]=densities[None]
                return densities[None]
            elif len(densities)==1:
                return densities.values()[0]
            elif fudge:
                return sum(densities.values())/len(densities)
            else:
                return None

    def parse_gramweight_measure (self, txt):
        m=self.gramwght_regexp.match(txt)
        if m:
            groups=m.groups()
            amt = groups[0]
            if amt: amt = float(amt)
            unit = groups[2]
            extra = groups[4]
            return amt,unit,extra

    def add_custom_nutrition_info (self, nutrition_dictionary):
        """Add custom nutritional information."""
        new_ndbno = self.db.increment_field(self.db.nview,'ndbno')
        if new_ndbno: nutrition_dictionary['ndbno']=new_ndbno
        self.db.do_add(self.db.nview,nutrition_dictionary)
        return self.db.nview[-1].ndbno
                    
class NutritionInfo:
    """A multipliable way to reference an object.

    Any attribute of object that can be mutiplied, will be returned
    multiplied by mult.

    We can also support various mathematical operators
    n = NutritionInfo(obj, mult=2)
    n * 2 -> NutritionInfo(obj,mult=4)
    n2 = NutritionInfo(obj2, mult=3)
    n2 + n -> NutritionInfoList([n2,n])

    The result is that addition and multiplication 'makes sense' for
    properties. For example, if we have nutrition info for 1 carrot,
    we can multiply it or add it to the nutrition info for an
    eggplant. The resulting object will reflect the appropriate
    cumulative values.

    Carrot = NutritionInfo(CarrotNutritionRow)
    Eggplant = NutritionInfo(EggplantNutritionRow)

    Carrot.kcal => 41
    Eggplant.kcal => 24
    (Carrot + Eggplant).kcal => 65
    (Carrot * 3 + Eggplant).kcal => 147

    This will be true for all numeric properties.

    Non numeric properties return a somewhat not-useful string:
    
    (Carrot + Eggplant).desc => 'CARROTS,RAW, EGGPLANT,RAW'
    """
    def __init__ (self,rowref, mult=1, fudged=False):
        self.__rowref__ = rowref
        self.__mult__ = mult
        self.__fudged__ = fudged

    def __getattr__ (self, attr):
        if attr[0]!='_':
            ret = getattr(self.__rowref__, attr)
            try:
                if attr in SUMMABLE_FIELDS:
                    return (ret or 0) * self.__mult__
                else:
                    return ret
            except:
                raise
        else:
            # somehow this magically gets us standard
            # attribute handling...
            raise AttributeError, attr

    def __add__ (self, obj):
        if isinstance(obj,NutritionInfo):
            return NutritionInfoList([self,obj])
        elif isinstance(obj,NutritionInfoList):
            return NutritionInfoList([self]+obj.__nutinfos__)

    def __mul__ (self, n):
        return NutritionInfo(self.__rowref__, self.__mult__ * n)

KEY_VAPOR = 0 # when we don't have a key
UNIT_VAPOR = 1 # when we can't interpret the unit
DENSITY_VAPOR = 2 # when we don't have a density
AMOUNT_VAPOR = 3 # when there is no amount, leaving us quite confused

class NutritionVapor (NutritionInfo):
    """An object to hold our nutritional information before we know it.

    Basically, we have to behave like a NutritionInfo class that doesn't
    actually return any data.

    We also can return information about why we're still vapor
    (whether we need density info, key info or what...).
    """
    def __init__ (self, nd, key,
                  rowref=None,
                  mult=None,
                  amount=None,
                  unit=None,):
        self.__nd__ = nd
        self.__rowref__ = rowref
        self.__key__ = key
        self.__mult__ = mult
        self.__amt__ = amount
        self.__unit__ = unit

    def _reset (self):
        """Try to create matter from vapor and return it.

        If we fail we return more vapor."""
        if not self.__rowref__:
            if self.__mult__:
                ni = self.__nd__.get_nutinfo(self.__key__)
                if not isinstance(ni,NutritionVapor): return ni * self.__mult__
                else: return self
            else:
                return self.__nd__.get_nutinfo_for_item(self.__key__,
                                                        self.__amt__,
                                                        self.__unit__)
        elif self.__amt__:
            c=self.__nd__.get_conversion_for_amt(self.__amt__,self.__unit__,self.__key__,fudge=False)
            if c:
                self.__mult__ = c
                return NutritionInfo(self.__rowref__,
                                     self.__mult__)
            else:
                c=self.__nd__.get_conversion_for_amt(self.__amt__,self.__unit__,self.__key__,fudge=True)
                if c:
                    self.__mult__ = c
                    return NutritionInfo(self.__rowref__,
                                         self.__mult__)
                else:
                    return self
        else: return self.__nd__.get_nutinfo_for_item(self.__key__,self.__amt__,self.__unit__)

    def __getattr__ (self,attr):
        """Return 0 for any requests for a non _ prefixed attribute."""
        if attr[0]!='_':
            return 0
        else:
            raise AttributeError,attr

    def __repr__ (self):
        return '<NutritionVapor %s>'%self.__key__
    
    def __nonzero__ (self):
        """Vapor is always False."""
        return False

    def _wheres_the_vapor (self):
        """Return a key as to why we're vapor."""
        if not self.__rowref__: return KEY_VAPOR
        elif not self.__amt__: return AMOUNT_VAPOR
        else: return UNIT_VAPOR
    
class NutritionInfoList (list, NutritionInfo):
    """A summable list of objects.

    When we ask for numeric attributes of our members, we get the sum.
    """
    def __init__ (self,nutinfos, mult=1):
        self.__nutinfos__ = nutinfos
        self.__len__ = self.__nutinfos__.__len__
        self.__getitem__ = self.__nutinfos__.__len__
        self.__mult__ = 1

    def __getattr__ (self, attr):
        if attr[0]!='_':
            alist = [getattr(ni,attr) for ni in self.__nutinfos__]
            if attr in SUMMABLE_FIELDS:
                if self.__mult__: alist = [n * self.__mult__ for n in alist]
                return sum(alist)
            else:
                return ", ".join(map(str,alist))
        else:
            # somehow this magically gets us standard
            # attribute handling...
            raise AttributeError, attr

    def _reset (self):
        """See if we can turn any of our vapor into matter."""
        for i in range(len(self.__nutinfos__)):
            obj = self.__nutinfos__[i]
            if isinstance(obj,NutritionVapor):
                # try resetting
                self.__nutinfos__[i]=obj._reset()

    def _get_vapor (self):
        """Return a list of nutritionVapor if there is any

        In other words, tell us whether we are missing any nutritional
        information."""
        ret = []
        for i in self.__nutinfos__:
            if isinstance(i,NutritionVapor): ret.append(i)
        return ret

    def _get_fudge (self):
        """Return a list of fudged items
        """
        ret = []
        for i in self.__nutinfos__:
            if hasattr(i,'__fudged__') and i.__fudged__:
                ret.append(i)
        return ret
        
    def __add__ (self, obj):
        if isinstance(obj,NutritionInfo):
            return NutritionInfoList(self.__nutinfos__ + [obj])
        elif isinstance(obj,NutritionInfoList):
            return NutritionInfoList(self.__nutinfos__ + obj.__nutinfos__)

    def __sub__ (self, obj):
        copy = self.__nutinfos__[0:]
        copy.remove(obj)
        return NutritionInfoList(copy)

    def __getslice__ (self, a, b):
        return NutritionInfoList(self.__nutinfos__[a:b])

    def __len__ (self): return len(self.__nutinfos__)

    def __repr__ (self):
        return '<NutritionInfoList>'
            
if __name__ == '__main__':
    import sys
    sys.path.append('/usr/share/')
    import gourmet.recipeManager as rm
    db=rm.RecipeManager(**rm.dbargs)
    import gourmet.convert
    conv = gourmet.convert.converter()
    import nutritionGrabberGui
    nutritionGrabberGui.check_for_db(db)
    nd=NutritionData(db,conv)

def foo ():
    from gourmet import convert
    class SimpleInterface:
        
        def __init__ (self, nd):
            self.ACTIONS = {'Add ingredient':self.add_ingredient,
                       'Add key info':self.add_key,
                       'Print info':self.print_info,
                       'Exit' : self.exit
                       }
            self.nd = nd
            self.ings = []

        def run (self):
            choices = self.ACTIONS.keys()
            for n,a in enumerate(choices):
                print n,a
            choice = None
            while not choice:
                choice = raw_input('Enter number of choice: ')
                choice = int(choice)
                if choice < len(choices): choice = self.ACTIONS[choices[choice]]
                else: choice = None
            try:
                choice()
            except:
                raise
            else:
                self.run()
                

        def add_ingredient (self):
            key=raw_input('Enter ingredient key: ')
            amt = convert.frac_to_float(raw_input('Enter amount: '))
            unit = raw_input('Enter unit: ')
            if not self.ings:
                self.ings = NutritionInfoList([self.nd.get_nutinfo_for_item(key,amt,unit)])
            else:
                self.ings = self.ings + self.nd.get_nutinfo_for_item(key,amt,unit)

        def add_key (self):
            key=raw_input('Enter key for which we add info: ')
            matches = self.nd.get_matches(key,10)
            for n,m in enumerate(matches):
                print n,'. ',m[0]
            choice = None
            while not choice:
                choice = raw_input('Enter number of choice: ')
                choice = int(choice)
                if choice < len(matches): choice = matches[choice][1]
                else: choice = None
            self.nd.set_key_from_ndbno(key,choice)
            self.ings._reset()

        def print_info (self):
            att = raw_input('What information would you like (e.g. kcal): ')
            while not hasattr(self.ings,att):
                print "I'm sorry, there is no information about ",att
                att = raw_input('What information would you like (e.g. kcal): ')
            print att,":",getattr(self.ings,att)
            vv = self.ings._get_vapor()
            if vv:
                print '(but we have some vapor)'
                for v in vv:
                    explanation = v._wheres_the_vapor()
                    print 'Vapor for ',v.__key__
                    if explanation==KEY_VAPOR: print 'No key'
                    if explanation==UNIT_VAPOR: print "Can't handle unit ",v.__unit__
                    if explanation==AMOUNT_VAPOR: print "What am I to do with the amount ",v.__amt__
                

        def exit (self):
            import sys
            sys.exit()
    si = SimpleInterface(nd)
    si.run()
    #import random
    #fake_key = "0"
    #while raw_input('Get another density?'):
    #    row=random.choice(db.nview)
    #    print 'Information: ',row.desc, nd.get_conversions(row=row)
    #    #print 'Gramweights: ',nd.get_gramweights(row)
    #    #print 'Density of ',row.desc,' = ',nd.get_densities(row)
