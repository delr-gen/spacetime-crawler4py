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
from difflib import SequenceMatcher

config = configparser.ConfigParser()
config.read("config.ini")
userAgent = config['IDENTIFICATION']['USERAGENT']
default_time = float(config['CRAWLER']['POLITENESS'])
polite_time = 0
sub_domains = defaultdict(int) 
largest_pg = ('',0) #(resp.url, word count) 
unique_links = set("https://www.ics.uci.edu","https://www.cs.uci.edu","https://www.informatics.uci.edu","https://www.stat.uci.edu") 
prev_urls = []
#prev_resps = []
word_freq = defaultdict(int)
prev_simhashes = []

def output_report():
    with open("output.txt", "w") as output_file:
        output_file.write(f"Number of unique pages: {len(unique_links)}.\n")
        output_file.write(f"The longest page is {largest_pg[0]} with {largest_pg[1]} words.\n")
        output_file.write(f"The 50 most common words: {sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[0:50]}.\n")
        output_file.write(f"Number of subdomains in ics.uci.edu: {sum(sub_domains.values())}\n")
        for k, v in sorted(sub_domains.items(), key=lambda x: x[0]):
            output_file.write(f"    {k}, {v}\n")


def report_info(text, url):
    #soup = BeautifulSoup(resp.raw_response.content.decode('utf-8','ignore'), "lxml")

    words = nltk.tokenize.word_tokenize(text.lower())

    global word_freq  # get most common words, excluding stop words
    word_freq = tokenizer.tokenizeCount(words, word_freq)

    #if resp.raw_response != None:
        #soup = BeautifulSoup(resp.raw_response.content, "lxml")
    #words = nltk.tokenize.word_tokenize(text)

    global largest_pg # check if correct
    if len(words) > largest_pg[1]: largest_pg = (url, len(words))

    # keep track of longest page
    global sub_domains
    parsed = urlparse(url)
    # if domain is ics.uci.edu
    if parsed.netloc[-12:] == '.ics.uci.edu' and parsed.netloc != 'www.ics.uci.edu':
        #check if this is correct
        url = urldefrag(url)[0]
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
    #report_info(resp) # figure out how to get this info to a file or something
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    urls = list()
    if resp.status != 200:
        print(resp.error)
        return urls
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content

    #if it is permitted to crawl the url, parse resp.raw_response.content for links
    #is_valid(url)
    
    # check if there is actually data associated with the url (make sure it is not a dead url)
    if resp.raw_response == None or len(resp.raw_response.content) == 0:
        return list()   

    # check if we visited the url before or if they are similar to previous urls
    parsed = urlparse(url)
    global prev_urls
    for prev_url in prev_urls:
        if resp.url == prev_url:return urls
        prev_parsed = urlparse(prev_url)
        if parsed.netloc == prev_parsed.netloc:
            if SequenceMatcher(None, parsed.path, prev_parsed.path).ratio() >= .90:  # might change threshold later
                # check query too?
                return urls

    soup = BeautifulSoup(resp.raw_response.content.decode('utf-8','ignore'), "lxml")
    resp_text = soup.get_text()

    # CHECK TEXT CONTENT
    # we can either check for very large files by seeing if it exceeds a certain word count we just reject it
    # if len(resp_text) > 20000: return urls
    # or
    # we can strip all the stop words from the page and see if the remaining word count is lower than a threshold which 
    # would make it so it has 'low' textual information 
    # if len(resp_text) after stripping stop words < 100: return urls
    # or we can do both

    if len(resp_text) > 2000: # considered large file
        if len(resp_text) > 20000: # very unlikely to not be low info
            return urls
        if len(tokenizer.remove_stop_words(resp_text.lower())) < 100: # considered low info
            return urls

    
    # check for near duplicate pages
    global prev_simhashes
    curr_simhash = simhash.Simhash(resp_text)
    for prev_simhash in prev_simhashes: 
        #prev_text = BeautifulSoup(prev_resp.raw_response.content.decode('utf-8','ignore'), "lxml").get_text()
        #if near_duplicate(prev_text, resp_text, 10): # might change threshold
        if prev_simhash.distance(curr_simhash) < 10:
            return urls
    prev_simhashes.append(curr_simhash)
        # we are using BeautifulSoup lxml to find all the a tags in the html file that also has a
        # href attribute which is used to contain links that link to different pages or sites
        # we then use get to get the link associated with the href attribute
    
    report_info(resp_text, resp.url)

    # parse resp.raw_response.content look into BeautifulSoup, lxml
    # resp.raw_response.content should be html content
    # we want all the a tags that have href attributes
    base = urldefrag(resp.url)[0]
    global unique_links
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
        unique_links.add(defrag) # Assumption: even if the link isn't traversable or valid, it is still a unique link that was visited/encountered,
        #so we are adding it to our list based on that
        urls.append(defrag)
    #prev_resps.append(resp) # not sure if its actually global var have ot check
    prev_urls.append(resp.url)
    
    return urls

def is_valid(url):
    # Decide whether to crawl this url or not.
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False
        query = parsed.query
        if "share=" == query[0:6] or "ical=" == query[0:5]:
            return False
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1|apk|war"
            + r"|thmx|mso|arff|rtf|jar|csv|img|jpeg|jpg|png"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz|ppsx|pps|ova)$", parsed.path.lower()):
            return False
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1|apk|war"
            + r"|thmx|mso|arff|rtf|jar|csv|img|jpeg|jpg|png"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz|ppsx|pps|ova)$", parsed.query.lower()):
            return False
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1|apk|war"
            + r"|thmx|mso|arff|rtf|jar|csv|img|jpeg|jpg|png"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz|ppsx|pps|ova).*$", parsed.query.lower()):
            return False
        if re.match(
            r".*/(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv|img|jpeg|jpg|png"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz|ppsx|pps|ova)/?.*$", parsed.path.lower()):
            return False
        if re.match(
            r".*/(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv|img|jpeg|jpg|png"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz|ppsx|pps|ova)/?.*$", parsed.query.lower()):
            return False
        # parse the hostname to check if the domain is ics.uci.edu, cs.uci.edu, informatics.uci.edu, stat.uci.edu
        # consider splitting by . and checking the last 3 elems in the list to see if it is a valid domain
        # may consider parsing in a different way later
        netloc_parse = parsed.netloc.split('.')
        domain = netloc_parse[-3:]
        if (domain[-2:] != ['uci','edu'] or (domain[0] not in ['ics', 'cs', 'stat', 'informatics'])):
            return False

        # have to check for traps look at teh paths? compare to previous urls? 
        if ('calendar' in url.lower()): return False # calendar is a trap
        if 'events' in parsed.path: return False
        if re.match(
            r".*/[0-9][0-9][0-9][0-9]\-[0-1][0-9]\-[0-3][0-9]/?.*$", parsed.path.lower()):
            return False # deal with calendar trap
        if '?share=' in parsed.query or 'date=' in parsed.query: return False

        #check the robots.txt file (does the website permit the crawl)
        robot = urljoin(url, '/robots.txt')
        # access the file
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robot)
        rp.read()
        if (rp.crawl_delay()): polite_time = rp.crawl_delay()
        else: polite_time = default_time
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
    except urllib.error.URLError:
        return False

def near_duplicate(pg1, pg2, threshold):
    # simhash code obtained from here: https://github.com/1e0ng/simhash
    # we imported the simhash lib to determine whether two pages are near duplicates or not
    # if the distance between the two pages are less than the threshold the two pages are 
    # considered near duplicates
    s1 = simhash.Simhash(pg1)
    s2 = simhash.Simhash(pg2)
    return s1.distance(s2) < threshold
