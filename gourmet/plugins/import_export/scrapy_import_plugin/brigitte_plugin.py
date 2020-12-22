from gourmet.plugin import PluginPlugin
import re

class BrigittePlugin (PluginPlugin):
    """ This is a plugin for the german Brigitte page to import recipes
    easily.
    """
    target_pluggable = 'scrapyWeb_plugin'
    internalName = 'brigitte'

    def do_activate (self, pluggable):
        pass
    
    def test_url (self, url, data):
        if 'brigitte.de' in url: 
            return 10
        return -99

    def get_parser (self):
        class Parser:
            def parse(self, selector):
                recipe = dict()
                recipe['source'] = "Brigitte"
                
                recipe['title'] = selector.css(".u-typo--article-title::text").extract_first()
                
                ingredientsWithGroups = []
                ingredients = []
                
                ingBlocks = selector.css(".o-article__ingredient-block")
                for block in ingBlocks:
                    head = block.xpath(".//h4/text()").extract_first()
                    if head and len(head) > 0:
                        gDict = { 'name':head, 'ingredients':[] }
                        ingredientsWithGroups.append( gDict )
                        ingredients = gDict['ingredients']
                    
                    for ing in block.xpath(".//li"):
                        amount = ing.xpath("@data-recipe-item-amount").extract_first()
                        unit = ing.xpath("@data-recipe-item-unit-singular").extract_first()
                        name = ing.xpath("@data-recipe-item-name-singular").extract_first()
                        add = ing.xpath("@data-recipe-item-name-suffix").extract_first()
                        if len(add) > 0:
                            add = "(" + add + ")"
                        
                        ingredients.append(" ".join( filter(lambda k: len(k) > 0, [amount, unit, name, add] )) )
                                    
                recipe['ingredients'] = ingredients if len( ingredientsWithGroups ) == 0 else ingredientsWithGroups
                recipe['servings'] = int(selector.css(".recipe-ingredients__value::text").extract_first().strip())
			
                
                total = selector.xpath("//time[@itemprop='totalTime']/text()").extract_first()
                m = re.search(u"([0-9]+)[\s\xa0\n]*(\S+)", total,re.MULTILINE | re.DOTALL)
                if m:
                    recipe['cooktime'] = " ".join( [m.group(1), m.group(2)])
                
                recipe['instructions'] = "\n\n".join( selector.css(".o-article__preparation-wrapper").xpath(".//span[@class='m-ordered-list-recipe__preparation-text']/text()").extract() )
                recipe['imageUrl'] = selector.css(".m-single-image--aufmacher").xpath(".//img/@src").extract_first()

                return recipe;

        return Parser()


