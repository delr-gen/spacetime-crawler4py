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
sub_domains = defaultdict(int) #{key: subdomain, value: # of unique pages}
largest_pg = ('',0) #(resp.url, word count) 
unique_links = set("https://www.ics.uci.edu","https://www.cs.uci.edu","https://www.informatics.uci.edu","https://www.stat.uci.edu") 
prev_urls = []
#prev_resps = []
word_freq = defaultdict(int) #{key: word, value: word count}
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

    # we reject any pages that do not have a 200 status
    # we will not crawl the page and therefore return an empty list
    if resp.status != 200:
        print(resp.error)
        return urls


    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content

    
    # we check if a response if given or if there is any content in the page to see if there 
    # is any data associated with the url/basically checking if it's a dead url 
    # if that is the case, we will not crawl the page and return an empty list                        
    if resp.raw_response == None or len(resp.raw_response.content) == 0:
        return list()   

    # we check if we visited the url before or if they are similar to previous urls
    parsed = urlparse(resp.url)
    global prev_urls
    for prev_url in prev_urls:
        # we compare the current url to all to the global list of all the previous urls 
        # we crawled to see if there is a match, an empty list is returned if there is a 
        # match because we will not crawl the page
        if resp.url == prev_url:return urls
        prev_parsed = urlparse(prev_url)
        # we then compare the paths of the current url to the paths of the previous urls
        # this is to make sure we do not end up in a trap where we are crawling a url
        # that has repeating paths and ultimately leads to a page that we have seen/crawled before
        if parsed.netloc == prev_parsed.netloc:
            # if netlocs of the urls are the same, we imported SequenceMatcher to check the 
            # similarities of the paths and if the ratio is above a threshold, we will not crawl the page
            if SequenceMatcher(None, parsed.path, prev_parsed.path).ratio() >= .90:  # might change threshold later
                # check query too?
                return urls

    # we used BeautifulSoup to get the text content of the page from resp.raw_response.content
    # we used .decode so it would ignore utf-8 errors
    soup = BeautifulSoup(resp.raw_response.content.decode('utf-8','ignore'), "lxml")
    resp_text = soup.get_text()
    resp_text_words = nltk.tokenize.word_tokenize(resp_text.lower())

    # we choose to not crawl any pages that are considered large files, but have low information value and return an empty list
    # we consider any files that exceed 2000 words to be a large file because pages on average are below or
    # around that word count
    if len(resp_text_words) > 2000:
        # we reject any pages with more than 20000 words because we believe that with how large the page is
        # it is very unlikely for it to not have low information value
        if len(resp_text_words) > 20000:
            return urls
        # if the page has between 2000 and 20000 words, we need more information to check if it has low information value
        # to do so, we take the words of the page and filter out any stop words and see how many words are left
        # if there are fewer that 100 words left, that means a large part of the page is filled with stop words
        # and therefore should be considered to have low information value and will be rejected.
        if len(tokenizer.remove_stop_words(resp_text_words)) < 100: # considered low info
            return urls

    
    # simhash code obtained from here: https://github.com/1e0ng/simhash
    # we imported the simhash library to determine whether two pages are near duplicates or not
    # if the distance between the two simhashes (it essentially looks at the difference between 
    # the two pages) is less than the threshold the two pages are considered near duplicates
    global prev_simhashes
    curr_simhash = simhash.Simhash(resp_text)
    for prev_simhash in prev_simhashes: 
        # we check if the current page is a near duplicate of any page we have seen before by comparing
        # its simhash to the simhashes of previous urls kept in a global list
        # if the current page is a near duplicate with any of the previous pages, we will not crawl the page
        # and return an empty list
        if prev_simhash.distance(curr_simhash) < 10:
            return urls
    prev_simhashes.append(curr_simhash)
        # we are using BeautifulSoup lxml to find all the a tags in the html file that also has a
        # href attribute which is used to contain links that link to different pages or sites
        # we then use get to get the link associated with the href attribute
    
    report_info(resp_text, resp.url)

    base = urldefrag(resp.url)[0]
    global unique_links
    global sub_domains

    # we are using BeautifulSoup with lxml to find all the a tags in the html file (resp.raw_response.content
    # contains the html content) that also has a href attribute which is used to contain links that link to 
    # different pages or sites 
    # we then use get to get the link associated with the href attribute as long as it is not '#' which means
    # the page links back to itself
    links = {a.get('href') for a in soup.find_all('a') if a.get('href')!="#"}
    for link in links:
        # the urls in the list have to be defragmented which can be done with urlparse.urldefrag
        # we have make sure to change relative urls to absolute urls 
        # these two steps need to be done before adding the url to the url list
        defrag = urldefrag(link)[0] # defrag link
        parsed = urlparse(defrag)
        
        # if the link does not have a netloc, it is most likely a relative url so we use urljoin to join it 
        # with resp.url to turn it into an absolute url
        if parsed.netloc == "":
            defrag = urljoin(base, defrag) 
        
        # we check for any unique pages that belongs to a subdomain of ics.uci.edu
        if parsed.netloc[-12:] == '.ics.uci.edu' and parsed.netloc != 'www.ics.uci.edu':
            # we check if the url is a subdomain of ics.uci.edu by looking at netloc
            sub_domain =  parsed._replace(fragment="", params="", query="",path="")
            # if the url is not in unique links, we have not found it so far so it can be counted as a unique page
            if defrag not in unique_links:
                # we parse out the subdomain using ._replace and urlunparse so it can be used as a key
                # we use the key in the global default dictionary so we can add to the count to indicate 
                # we found a unique page for this subdomain
                sub_domain = urlunparse(sub_domain)
                sub_domains[sub_domain] += 1
        # Assumption: even if the link isn't traversable or valid, it is still a unique link that was seen/encountered,
        # so we are adding it as a unique link based on that
        unique_links.add(defrag) 

        urls.append(defrag)

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
        if '?share=' in parsed.query or 'date=' in parsed.query: return False
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
