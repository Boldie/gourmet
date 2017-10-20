from gourmet.plugin import PluginPlugin
import re

class BildDerFrauPlugin (PluginPlugin):
    """ This is a plugin for the german BildDerFrau page to import recipes
    easily.
    """
    target_pluggable = 'scrapyWeb_plugin'
    internalName = 'bildderfrau'

    def do_activate (self, pluggable):
        pass
    
    def test_url (self, url, data):
        if 'bildderfrau.de' in url: 
            return 10
        return -99

    def get_parser (self):
        class Parser:
            def parse(self, selector):
                recipe = dict()
                recipe['source'] = "Bild der Frau"
                
                recipe['title'] = selector.css(".article__header__headline::text").extract_first()
                recipe['ingredients'] = selector.css(".zutaten-list").xpath('li//span//text()').extract()
                
                m = re.match(u'Zutaten f\xfcr (\d+) Portionen', selector.xpath('//h3[@class="icon__zutaten"]/text()').extract()[0])
                recipe['servings'] = int(m.group(1)) if m else 0
                
                recipe['cooktime'] = selector.xpath('//div[h3[text()[contains(.,"Koch-/Backzeit")]]]/ul/li/text()').re_first(r'(\d+ Minuten)')
                recipe['preptime'] = selector.xpath('//div[h3[text()[contains(.,"Zubereitungszeit")]]]/ul/li/text()').re_first(r'(\d+ Minuten)')

                
                
                recipe['instructions'] = "\n\n".join( selector.xpath('//h2[contains(@id,"Und-so-wird")]/following-sibling::ol/li/text()').extract() )
                recipe['imageUrl'] = selector.xpath("//figure/picture/source/@srcset")[2].extract()

                return recipe;

        return Parser()


