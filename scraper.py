import re
from urllib.parse import urlparse, urljoin, urldefrag, urlunparse
from bs4 import BeautifulSoup
import lxml
import urllib.robotparser
import nltk
# import time
import configparser
from collections import defaultdict
import simhash
import tokenizer

config = configparser.ConfigParser()
config.read("config.ini")
userAgent = config['IDENTIFICATION']['USERAGENT']
defaulttime = float(config['CRAWLER']['POLITENESS'])
sub_domains = defaultdict(int) 
largest_pg = ('',0) #(resp, word count) 
unique_links = set() 
prev_urls = []
prev_resps = []
word_freq = defaultdict(int)
most_common_words = []

def report_info(resp):
    global word_freq
    word_freq = tokenizer.tokenizeCount(resp, word_freq)
    global most_common_words
    most_common_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[0:50]
    if resp.raw_response != None:
        soup = BeautifulSoup(resp.raw_response.content, "lxml")
        words = nltk.tokenize.word_tokenize(soup.get_text())
        global largest_pg # check if correct
        if len(words) > largest_pg[1]: largest_pg = (resp, len(words))
    # keep track of longest page
    global sub_domains
    parsed = urlparse(resp.url)
    # if domain is ics.uci.edu
    if parsed.netloc[-12:] == '.ics.uci.edu' and parsed.netloc != 'www.ics.uci.edu':
        #check if this is correct
        url = resp.url.urldefrag()[0]
        parsed =  parsed._replace(fragment="", params="", query="",path="")
        # assuming the url has not been crawled before
        if url not in unique_links:
            sub_domain = urlunparse(parsed)
            sub_domains[sub_domain] += 1
    # add the subdomain in a dictionary add to count
    # key: subdomain value: unique pgs
    # sort alphabetically

def scraper(url, resp):
    # maybe keep track of prev urls in a list/set not sure
    # maybe keep a check to see if we've been to the url before?
    # if we have just return an empty list
    # this could be done in the for loop that loops over list returned by extract_next_links
    # maybe add a check for text content here and if there isnt much just dont call extract_next_link
    report_info(resp) # figure out how to get this info to a file or something
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    if resp.status != 200:
        print(resp.error)
        return urls
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content

    #if it is permitted to crawl the url, parse resp.raw_response.content for links
    #is_valid(url)
    urls = list()
        # check if there is actually data associated with the url (make sure it is not a dead url)
    if resp.raw_response != None and len(resp.raw_response.content) == 0:
        return list()
        

    # check if we visited the url before
    for prev_url in prev_urls:
        if resp.url == prev_url:return urls

    soup = BeautifulSoup(resp.raw_response.content, "lxml")
    resp_text = soup.get_text()

    # CHECK TEXT CONTENT
    # we can either check for very large files by seeing if it exceeds a certain word count we just reject it
    # if len(resp_text) > 50000: return urls
    # or
    # we can strip all the stop words from the page and see if the remaining word count is lower than a threshold which 
    # would make it so it has 'low' textual information 
    # if len(resp_text) after stripping stop words < 100: return urls
    # or we can do both

    if len(resp_text) > 2000: # considered large file
        if len(resp_text) > 50000: # very unlikely to not be low info
            return urls
        if len(tokenizer.remove_stop_words(resp_text)) < 100: # considered low info
            return urls

    
    # check for near duplicate pages
    for prev_resp in prev_resps: 
        prev_text = BeautifulSoup(prev_resp.raw_response.content, "lxml").get_text()
        if near_duplicate(prev_text, resp_text, 10): # might change threshold
            return urls
        # we are using BeautifulSoup lxml to find all the a tags in the html file that also has a
        # href attribute which is used to contain links that link to different pages or sites
        # we then use get to get the link associated with the href attribute

    # parse resp.raw_response.content look into BeautifulSoup, lxml
    # resp.raw_response.content should be html content
    # we want all the a tags that have href attributes
    base = urldefrag(resp.url)[0] # not sure if need to defrag base
    links = {a.get('href') for a in soup.find_all('a') if a.get('href')!="#"}
    for link in links:
            #the urls in the list have to be defragmented which can be done with urlparse.urldefrag
            #make sure to change relative urls to absolute urls (look into urljoin)
            #these two steps need to be done before adding it to the url list
        defrag = urldefrag(link)[0] # defrag link     
        parsed = urlparse(defrag)
        if parsed.netloc == "":
            defrag = urljoin(base, defrag) # join the base to link that is found/ check if this is working correctly if not add / to beginning of url
            # it essentially ensures that we will have the absolute url and not the relative url
        urls.append(defrag)
        # time.sleep(defaulttime)
    global prev_resps
    prev_resps.append(resp) # not sure if its actually global var have ot check
    global prev_urls
    prev_urls.append(resp.url)
    global unique_links
    unique_links.add(base)
    return urls

def is_valid(url):
    # Decide whether to crawl this url or not.
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower()):
            return False
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.query.lower()):
            return False
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz).*$", parsed.query.lower()):
            return False
        if re.match(
            r".*/(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)/?.*$", parsed.path.lower()):
            return False
        if re.match(
            r".*/(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)/?.*$", parsed.query.lower()):
            return False
        # parse the hostname to check if the domain is ics.uci.edu, cs.uci.edu, informatics.uci.edu, stat.uci.edu
        # consider splitting by . and checking the last 3 elems in the list to see if it is a valid domain
        # may consider parsing in a different way later
        netloc_parse = parsed.netloc.split('.')
        domain = netloc_parse[-3:]
        if (domain[-2:] != ['uci','edu'] or (domain[0] not in ['ics', 'cs', 'stat', 'informatics'])):
            return False

        # have to check for traps look at teh paths? compare to previous urls? 
        if 'calendar' in url: return False # calendar is a trap
        if re.match(
            r".*/[0-9][0-9][0-9][0-9]\-[0-1][0-9]\-[0-3][0-9]/?.*$", parsed.path.lower()):
            return False # deal with calendar trap
 
        #check the robots.txt file (does the website permit the crawl)
        robot = urljoin(url, '/robots.txt')
        # access the file
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robot)
        rp.read()
        if rp.can_fetch(userAgent, url): return True
        else: return False
        # return not re.match(
        #     r".*\.(css|js|bmp|gif|jpe?g|ico"
        #     + r"|png|tiff?|mid|mp2|mp3|mp4"
        #     + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
        #     + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
        #     + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
        #     + r"|epub|dll|cnf|tgz|sha1"
        #     + r"|thmx|mso|arff|rtf|jar|csv"
        #     + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())
    except TypeError:
        print ("TypeError for ", parsed)
        raise

def near_duplicate(pg1, pg2, threshold):
    # simhash code obtained from here: https://github.com/1e0ng/simhash
    # we imported the simhash lib to determine whether two pages are near duplicates or not
    # if the distance between the two pages are less than the threshold the two pages are 
    # considered near duplicates
    s1 = simhash.Simhash(pg1)
    s2 = simhash.Simhash(pg2)
    return s1.distance(s2) < threshold

def politenessCheck(url):
    robot = urljoin(url, '/robots.txt')
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robot)
    rp.read()
    if (rp.crawl_delay(userAgent)):
         return rp.crawl_delay(userAgent)
    else:
         return defaulttime
