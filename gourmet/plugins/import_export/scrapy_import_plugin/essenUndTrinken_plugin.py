from gourmet.plugin import PluginPlugin
import re

class EssenUndTrinkenPlugin (PluginPlugin):
    """ This is a plugin for the german Essen & Trinken page to import recipes
    easily.
    """
    target_pluggable = 'scrapyWeb_plugin'
    internalName = 'essenUndTrinken'

    def do_activate (self, pluggable):
        pass
    
    def test_url (self, url, data):
        if 'essen-und-trinken.de' in url: 
            return 10
        return -99

    def get_parser (self):
        class Parser:
            def parse(self, selector):
                recipe = dict()
                recipe['source'] = "Essen & Trinken"
                
                recipe['title'] = selector.xpath("//span[@class='headline-title']/text()").extract()[0]
                ingsRaw = selector.xpath('//ul[@class="ingredients-list"]/li')
                ingredientsWithGroups = []
                ingredients = []
                for ing in ingsRaw:
                    group = ing.css(".ingredients-zwiti::text").extract_first()
                    if group != None and len(group) > 0:
                        # We have a group
                        gDict = { 'name':group, 'ingredients':[] }
                        ingredientsWithGroups.append( gDict )
                        ingredients = gDict['ingredients']
                    else:
                        ingredients.append( re.sub( "\s{2,}", " ",   ing.css("::text").extract_first().strip() ) )
                        
                recipe['ingredients'] = ingredients if len( ingredientsWithGroups ) == 0 else ingredientsWithGroups 
                recipeYield = selector.css('.servings::text').extract_first()
                recipeYield = [int(s) for s in recipeYield.split() if s.isdigit()]
                if len(recipeYield) != 1:
                    raise RuntimeError("Unable to parse yield from webpage!")

                recipe['servings'] = recipeYield[0]
                recipe['cooktime'] = selector.css(".time-preparation::text").re_first(r'(\d+ \w+)')
                
                recipe['instructions'] = "\n\n".join( selector.xpath('//ul[@class="preparation"]/li/div/text()').extract() )
                recipe['imageUrl'] = "http:" + selector.xpath("//figure[@class='recipe-img']/img/@data-fullimage").extract_first()

                return recipe;

        return Parser()


