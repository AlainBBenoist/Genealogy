import sys
import os
import requests
import re
import logging
import unicodedata
from time import sleep
from bs4 import BeautifulSoup
import tools


## TODO
## Parsing start_time, end_time
## Parsing details have changed
## Costs & hours may not work as well as telephone 

logger = logging.getLogger(__name__)
REQUEST_DELAY=3.0                       # Delay in seconds between requests to geneanet

def parse_unions(section):
    """
    Retrieve Union details and children
    """
    unions = list()
    #print(section)
    
    try :
        for li in section.find_all('li', recursive=False):
            union = dict()
            # Retrieve information about union
            union['description'] = unicodedata.normalize('NFKC', li.get_text()).strip()
            item = li.find('a')
            if item:
                name = item.get_text()
                url = item.get('href')
                union['partner']={'name' : name, 'url' : url}
               
            # Find children
            child_li = li.find('ul')
            children = list()
            for child in child_li.find_all('li'):
                try :
                    img_item = child.find('img')
                    gender = child.img.get('alt') if img_item else ''
                    name = child.a.get_text()
                    url = child.a.get('href')
                    bdo_item = child.find('bdo')
                    bdo = bdo_item.get_text() if bdo_item else ''
                    children.append({'gender' : gender, 'name' : name, 'url' : url, 'bdo' : bdo})
                except:
                    pass
            union['children'] = children
            unions.append(union)
    except:
        pass
            
    return unions
            
def parse_parents(section):
    """
    Retrieve parents from a section
    """
    parents=list()
    try :
        for item in section.find_all('li'):
            #print('parent:')
            #print(item)
            name = item.a.get_text()
            url = item.a.get('href')
            bdo_item = item.find('bdo')
            bdo = bdo_item.get_text() if bdo_item else ''
            parents.append({'name' : name, 'url' : url, 'bdo' : bdo})
    except:
        pass
    return parents[0:2]

def parse_individual(*args):
    website = 'https://gw.geneanet.org/'
    
    current_url = args[0]
    if current_url and not current_url.startswith('http'):
        current_url = website + current_url
        
    data = dict()

    logger.debug(current_url)
    
    headers=tools.get_credentials(None, None)
    sleep(REQUEST_DELAY)
    page = requests.get(current_url, headers=headers)
    if page.status_code > 200 :
        logger.warning('{:s}: Error {:d}'.format(current_url, page.status_code))
        return None
    #page.encoding='utf-8'

    # Retrieve the page 
    soup = BeautifulSoup(page.text, 'html.parser')

    # Find first name and last name
    try :
        data['gender'] = soup.find('div', id='person-title').h1.img.get('title')
        list_a = soup.h1.find_all('a')
        if len(list_a) >= 2:
            data['first_name'] = list_a[0].get_text()
            data['last_name'] = list_a[1].get_text()
            #print(data['first_name']+' '+data['last_name'], file=sys.stderr)
    except:
        return data
    
    # Sosa
    try :
        data['sosa']=unicodedata.normalize('NFKC', soup.find('em', class_='sosa').a.get_text())
    except:
        pass

    # Description Text
    data['birth_date'] = data['death_date'] = ''
    ul = soup.h1.find_next('ul')
    try :
        for item in ul.find_all('li', recursive=False):
            # Remove special characters like 0xa0
            text=unicodedata.normalize('NFKC', item.get_text())
            # Determine type of text
            if text.startswith('Né ') or text.startswith('Née '):
                data['birth'] = text
                data['birth_date'] = get_date(text, year_only=True)
                data['birth_place'] = get_place(text)
            elif text.startswith('Décédé ') or text.startswith('Décédée '):
                data['death'] = text
                data['death_date'] = get_date(text, year_only=True)
                data['death_place'] = get_place(text)
            elif text.startswith('Baptisé ') or text.startswith('Baptisée '):
                data['baptized'] = text
            elif text.startswith('Inhumé ') or text.startswith('Inhumée '):
                data['buried'] = text
            else :
                data['description'] = text
            #print(text)
    except:
        pass

    # Process useful h2 sections 
    for h2 in soup.find_all('h2') :
        section_name = h2.get_text()
        if 'Parents' in section_name:
            #print(section_name, file=sys.stderr)
            parents_section = h2.find_next_sibling('div', id='parents')
            if not parents_section :
                parents_section = h2.find_next_sibling('ul')
            data['parents'] = parse_parents(parents_section)
        elif 'enfant(s)' in section_name:
            #print(section_name, file=sys.stderr)
            data['unions'] = parse_unions(h2.find_next_sibling('ul', class_='fiche_union'))
        
    #print(soup.prettify())

    return data


url_set_descent = set()
def print_descent(url, depth):

    mark = '*' if url in url_set_descent else '>'
    url_set_descent.add(url)
    padding=mark.rjust(depth*4)
    
    data = parse_individual(url)
    #print(data)

    if data and 'last_name' in data:
        birth_date = data['birth_date'] if 'birth_date' in data else ''
        death_date = data['death_date'] if 'death_date' in data else ''
        """
        print('{:s}{:s} {:s} {:s}-{:s}'.format(padding, data['first_name'], data['last_name'], birth_date, death_date))
        """
        if 'birth' in data:
            print('{:s} => {:s}'.format(data['birth'], get_place(data['birth'])))
        if 'death' in data:
            print('{:s} => {:s}'.format(data['death'], get_place(data['death'])))
        
        if 'unions' in data:
            for union in data['unions']:
                #print(union)
                if 'children' in union:
                    for child in union['children']:
                        print_descent(child['url'], depth+1)
                        
url_set_ascent = set()
def print_ascent(url, depth):

    mark = '*' if url in url_set_ascent else '>'
    url_set_ascent.add(url)
    padding=mark.rjust(depth*4)
    
    data = parse_individual(url)
    #print(data)

    if data and 'last_name' in data:
        print('{:s}{:s} {:s}'.format(padding, data['first_name'], data['last_name']))
        if 'parents' in data:
            for parent in data['parents']:
                print_ascent(parent['url'], depth+1)

def get_date(text, year_only=False) :
    """
    Extracts a date from a string
    Ex: 13 janvier 1946
    """
    month_map={
                'janvier' : '01',
                'février' : '02',
                'fevrier' : '02',
                'mars' : '03',
                'avril' : '04',
                'mai' : '05',
                'juin' : '06',
                'juillet' : '07',
                'août' : '08',
                'aout' : '08',
                'septembre' : '09',
                'octobre' : '10',
                'novembre' : '11',
                'décembre' : '12',
                'decembre' : '12',
            }
    prefix_map= {
                 'après' : '>',
                 'apres' : '>',
                 'avant' : '<',
                 'vers' : '~',
                 'peut-être' : '?',
                }
    reg_search = [ r'(?P<prefix>vers|avant|apres|après|peut\-être)?(?P<day>\d{1,2})?(er)?\s*(?P<month>janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)?\s*(?P<year>\d{4})', ]
    for reg in reg_search :
        result = re.search(reg, text.lower())
        if result :
            pre = result.group('prefix')
            prefix = prefix_map[pre] if pre and pre in prefix_map else ''
            day = result.group('day')
            mo = result.group('month')
            month = month_map[mo] if mo and mo in month_map else None
            year = result.group('year')
            if year_only:
                return prefix+year
            elif day and month:
                return prefix+day+'/'+month+'/'+year
            elif month:
                return prefix+month+'/'+year
            else:
                return prefix+year
    return ''

def get_place(text):
    """
    Extracts a place from a string
    Ex: - Sainte-Cécile, 50800, Manche, Basse-Normandie, France
    todo : -' sep
    """
    reg_search = [ r'\-\s+(?P<city>(\-|\s|\w)+)\,\s+(?P<zipcode>\d{4,6})\,\s*(?P<dept>(\-|\s|\w)+)\,\s+(?P<region>(\s|\-|\w)+)\,\s+(?P<country>(\-|\w)+)',
                   r'\-\s+(?P<city>(\-|\s|\w)+)\,\s*(?P<dept>(\-|\s|\w)+)\,\s+(?P<region>(\s|\-|\w)+)\,\s+(?P<country>(\-|\w)+)']
    for reg in reg_search :
        result = re.search(reg, text)
        if result :
            place = result.groupdict(default='')
            return place['city'] if 'city' in place else ''
    return ''

def query_individuals(last_name, first_name, place='', birth_date='', death_date='', gender=''):
    """
    This function returns a list of individals matching a last_name, first_name
    """
    website='https://www.geneanet.org'
    
    # Transformation of parameters into suitable url variables
    lname_var = last_name.lower()
    fname_var = '+'.join(first_name.lower().split(' '))
    place_var = place.lower()
    from_var = birth_date
    to_var = death_date

    # Building query url
    URL_FMT='{:s}/fonds/individus/?sexe={:s}&nom={:s}&prenom={:s}&prenom_operateur=or&place__0__={:s}&type_periode=between&from={:s}&to={:s}&go=1'
    query_url = URL_FMT.format(website, gender, lname_var, fname_var, place_var, from_var, to_var)
    #query_url='https://www.geneanet.org/fonds/individus/?sexe=&nom=villain&ignore_each_patronyme=&prenom=georges+emile&prenom_operateur=or&ignore_each_prenom=&place__0__=&zonegeo__0__=&country__0__=&region__0__=&subregion__0__=&place__1__=&zonegeo__1__=&country__1__=&region__1__=&subregion__1__=&place__2__=&zonegeo__2__=&country__2__=&region__2__=&subregion__2__=&place__3__=&zonegeo__3__=&country__3__=&region__3__=&subregion__3__=&place__4__=&zonegeo__4__=&country__4__=&region__4__=&subregion__4__=&type_periode=between&from=&to=&exact_day=&exact_month=&exact_year=&go=1'
    headers=tools.get_credentials(None, None)
    results = set()
    
    while 'there are pages':
        #print(query_url)
        sleep(REQUEST_DELAY)
        page = requests.get(query_url, headers=headers)
        if page.status_code > 200 :
            logger.warning('{:s}: Error {:d}'.format(current_url, page.status_code))
            return None
        page.encoding='utf-8'
        soup = BeautifulSoup(page.text, 'html.parser')
        
        # Retrieve the results
        table = soup.find('div', id='table-resultats')
        #print(table.prettify())
        for item in table.find_all('a', class_='ligne-resultat', recursive=False):
            url = item.get('href')
            discard = False if url.startswith('https://gw.geneanet.org/') else True
            """
            discard=False
            for marker in ['/releves-collaboratifs/',
                           '/archives/registres/',
                           '/archives/etat-civil/',
                           '/archives/livres/',
                           '/ressources_externes/popup/',
                           '/cimetieres/view/',
                           'javascript:window.searchResultsUtils' ]:
                if marker in url:
                    discard = True
            """
            if discard:
                continue

            results.add(url)
            #print(url)
            line=''
            # Collect information
            for text in item.find_all('div', class_='text-large'):                
                full_text = text.get_text().strip()
                if full_text.startswith('Période :'):
                    full_text = full_text[9:].strip()
                line += '\t'+full_text
            # Find owner of genealogic tree
            source=item.find('div', class_='sourcename')
            if source:
                line += '\t'+source.get_text().strip()
            #print(line)
            
        # Retrieve url of next page
        try :
            ul = soup.find('ul', class_='pagination')
            #print(ul)
            current = ul.find('li', class_='current')
            #print(current)
            next_arrow = current.find_next('li', class_='arrow')
            #print(next_arrow)
            next_url=next_arrow.a.get('href')
            query_url = website+next_url
        except :
            return results
        
    return results


def match_individuals(ref_ind, cdt_ind):
    ratio = 1.0
    if not ref_ind or not cdt_ind:
        return 0.0
    if 'first_name' not in ref_ind or 'first_name' not in cdt_ind:
        return 0.0
    if ref_ind['first_name'] != cdt_ind['first_name']:
        ratio = 0.6
    if 'birth_date' in ref_ind and 'birth_date' in cdt_ind:
        ratio *= 1.0 if ref_ind['birth_date'] == cdt_ind['birth_date'] else 0.8
    if 'death_date' in ref_ind and 'death_date' in cdt_ind:
        ratio *= 1.0 if ref_ind['death_date'] == cdt_ind['death_date'] else 0.8
    if 'birth_place' in ref_ind and 'birth_place' in cdt_ind:
        ratio *= 1.0 if ref_ind['birth_place'] == cdt_ind['birth_place'] else 0.8
    return ratio

reviewed = set()
def find_missing_ascend(url):
    """
    Finding on geneanet information for individuals for which we are currently missing parents
    :param url:
    :return:
    """
    # Find data regarding the first individual
    data = parse_individual(url)

    # Avoid processing the same url several times 
    if url in reviewed:
        return False
    else :
        reviewed.add(url)
        
    if data and 'last_name' in data:
        if 'parents' in data:
            for parent in data['parents']:
                find_missing_ascend(parent['url'])
        else :
            if 'birth_place' in data and len(data['birth_place']) > 0:
                place = data['birth_place']
            elif 'death_place' in data and len(data['death_place']) > 0:
                place = data['death_place']
            else:
                place = ''
            birth_date = data['birth_date'] if 'birth_date' in data else ''
            death_date = data['death_date'] if 'death_date' in data else ''
            print('{:s} {:s} {:s}-{:s} {:s}'.format(data['last_name'], data['first_name'], birth_date, death_date, place))
            # Search for that individual on geneanet (other gen. trees)
            if len(place) > 0 and (len(birth_date) > 0 or len(death_date) > 0) :
                for ind_url in query_individuals(data['last_name'], data['first_name'], place=place, birth_date=birth_date, death_date=death_date):
                    #print('\t'+ind_url)
                    ind_data = parse_individual(ind_url)
                    # Verify that the individual matches the one we are looking for
                    # Check dates and location
                    # if not ok move to the next one
                    if match_individuals(data, ind_data) < 0.6:
                        continue
                    if 'parents' in ind_data:
                        birth_place = ind_data['birth'] if 'birth' in ind_data else ''
                        birth_date = ind_data['birth_date'] if 'birth_date' in ind_data else ''
                        death_date = ind_data['death_date'] if 'death_date' in ind_data else ''
                        print('\t{:s} {:s} {:s}-{:s} {:s} {:s}'.format(ind_data['last_name'], ind_data['first_name'], birth_date, death_date, birth_place, ind_url))
                        
                        for parent in ind_data['parents']:
                            par_data = parse_individual(parent['url'])
                            if not par_data or 'last_name' not in par_data:
                                continue
                            birth_place = par_data['birth'] if 'birth' in par_data else ''
                            birth_date = par_data['birth_date'] if 'birth_date' in par_data else ''
                            death_date = par_data['death_date'] if 'death_date' in par_data else ''
                            print('\t\t{:s} {:s} {:s}-{:s} {:s}'.format(par_data['first_name'], par_data['last_name'], birth_date, death_date, birth_place))
                            #key=input('>>')

                

if __name__ == '__main__':
    stem = os.path.splitext(os.path.basename(__file__))[0]
    logging.basicConfig(filename=stem+'.log',
                        filemode='w',
                        level=logging.DEBUG,
                        format='%(asctime)s %(levelname)-10s %(module)s:%(lineno)03d %(message)s',
                        datefmt='%Y/%m/%d %H:%M:%S')
    dates = [   'Née le 11 janvier 2002',
                '01 février 2001',
                ' mars 1999',
                '1er mars 1996',
                '2000',
            ]
    places = [ '- Montbray, 50410, Manche, Basse-Normandie, FRANCE',
            ]

    #find_missing_ascend('https://gw.geneanet.org/sbenoist?n=benoist&oc=&p=henri+emile')
    #find_missing_ascend('https://gw.geneanet.org/alainb7_w?lang=fr&pz=chloe+julie&nz=benoist&p=veronique+jacqueline+florence&n=villain')
    #find_missing_ascend('https://gw.geneanet.org/alainb7_w?lang=fr&pz=chloe+julie&nz=benoist&p=leontine+victorine&n=marquet')
    find_missing_ascend('https://gw.geneanet.org/9x5an?n=le+herpeur&oc=&p=perrine')
    """    
    for place in places:
        print(get_place(place))
    sys.exit(1)

    
    results = query_individuals('Villain', 'Georges Emile', birth_date='1901', death_date='1985', place='Margueray')
    print('{:d} results'.format(len(results)))
          
    sys.exit(1)
    """
    

    # Tester les cas suivants :
    # 1. Pas de mariage - pas d'enfant
    # 2. Un mariage
    # 3. Plusieurs mariages
    # 4. Un mariage sans enfants
    # 5. Pas de parents
    
    # Test Parsing
    urls = [ #'https://gw.geneanet.org/alainb7_w?lang=fr&pz=chloe+julie&nz=benoist&p=bernadette&n=monthurel', # Pas de mariage-pas d'enfants
             #'https://gw.geneanet.org/alainb7_w?lang=fr&pz=chloe+julie&nz=benoist&p=guillaume+dit+le+conquerant&n=de+normandie', # un mariage
             #'https://gw.geneanet.org/sbenoist?lang=fr&p=guillaume+le+conquerant&n=de+normandie',
             #'https://gw.geneanet.org/nlargier?lang=fr&pz=nicole&nz=largier&p=adele+d&n=angleterre+ou+de+normandie+ou+de+blois',
             #'https://gw.geneanet.org/alainb7_w?lang=fr&pz=chloe+julie&nz=benoist&p=rolon&n=de+normandie',
             #'https://gw.geneanet.org/alainb7_w?lang=fr&pz=chloe+julie&nz=benoist&p=louise+blandine+francoise&n=monhurel', # Pas de mariage-2 enfants
             #'https://gw.geneanet.org/alainb7_w?lang=fr&pz=chloe+julie&nz=benoist&p=leontine+victorine&n=marquet', # 2 mariages avec enfants
             #'https://gw.geneanet.org/alainb7_w?lang=fr&pz=chloe+julie&nz=benoist&p=guillaume&n=vimont', # Pas de parents
             #'https://gw.geneanet.org/alainb7_w?lang=fr&pz=chloe+julie&nz=benoist&p=rene+henri+dit+le+grand+gars&n=honore',
             #'https://gw.geneanet.org/9x5an?n=le+herpeur&oc=&p=perrine',
             ]
    for url in urls :
        print_descent(url, 0)
##      data = parse_individual(url)
##      if data and 'last_name' in data:
##          print('{:s} {:s}'.format(data['first_name'], data['last_name']))
##          #print(data)
