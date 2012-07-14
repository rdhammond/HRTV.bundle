import re

PREFIX			= "/video/hrtv"
TITLE			= "HRTV"
ART				= 'art-default.jpg'
ICON_DEFAULT	= 'icon-default.png'
ICON_PREFS		= 'icon-prefs.png'
LIVE_DEFAULT	= 'icon-tv.png'
ICON_SEARCH		= 'icon-search.png'

VIDEO_FEED		= 'http://www.hrtv.com/ajax/videos/ajax.aspx?mode=VideoPage'

REGEX_WIDTH		= Regex('width=[0-9]+')
REGEX_HEIGHT	= Regex('height=[0-9]+')
REGEX_RTMP		= re.compile('^(?P<rtmp>rtmp.*)(?P<clip>mp4:.*)\.mp4$', re.I)

def Start():
	Dict.Reset()
	HTTP.CacheTime = CACHE_1HOUR
	HTTP.Headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:12.0) Gecko/20100101 Firefox/12.0'
	HTTP.ClearCookies()

@handler(PREFIX, TITLE, thumb = ICON_DEFAULT, art = ART)
def MainMenu():
	oc = ObjectContainer()
	oc.add(DirectoryObject(key = Callback(LiveStream), title = "Live Stream", thumb = R(ICON_DEFAULT)))
	oc.add(DirectoryObject(key = Callback(VideoVault), title = "Video Vault", thumb = R(ICON_DEFAULT)))
	oc.add(PrefsObject(title = "Preferences", thumb = R(ICON_PREFS)))
	return oc

def LiveStream():
	loginResult = HRTVLogin()
	Log("Login success: " + str(loginResult))
	
	if loginResult:
		html = HTML.ElementFromURL("http://www.hrtv.com/videos/?ls=y", cacheTime = 0)
		url = html.xpath('//iframe[contains(@src, "robertsstream.com")]/@src')[0]
		url = REGEX_WIDTH.sub('width=720', url)
		url = REGEX_HEIGHT.sub('height=450', url)

		oc = ObjectContainer()
		
		oc.add(VideoClipObject(
			url = url,
			title = "Live Stream",
			thumb = R(LIVE_DEFAULT),
			items = [
				MediaObject(parts = [PartObject(key = WebVideoURL(url))])
			]
		))
		
		return oc
	else:
		return ObjectContainer(header = "Video Unavailable", message = "A login is required for this resource.")
	
def HRTVLogin():
	username = Prefs["username"]
	password = Prefs["password"]
	
	if (username != None) and (password != None):
		authentication_url = "https://www.hrtv.com/members/login/"
		resp = HTTP.Request(authentication_url, cacheTime=0).content
		
		current_session = ''
		for item in HTTP.CookiesForURL('https://www.hrtv.com/').split(';'):
				if 'ASP.NET_SessionId' in item:
					current_session = item
		Log("current_session = " + current_session)
		
		if (Dict['ASP.NET_SessionId'] != None) and (Dict['ASP.NET_SessionId'] == current_session):
			Log('Dict["ASP.NET_SessionId"] = ' + Dict['ASP.NET_SessionId'])
			return True

		HTTP.ClearCookies()
		resp = HTTP.Request(authentication_url, cacheTime=0).content
		html = HTML.ElementFromString(resp)
		event_validation = html.xpath('//input[@name="__EVENTVALIDATION"]/@value')[0]
		view_state = html.xpath('//input[@name="__VIEWSTATE"]/@value')[0]

		values = {'__EVENTTARGET': '',
					'__EVENTARGUMENT': '',
					'CT_Header$ccTopNav$rptNav$ctl00$ccSubNav$hdn': '1',
					'CT_Header$ccTopNav$rptNav$ctl01$ccSubNav$hdn': '3',
					'CT_Header$ccTopNav$rptNav$ctl02$ccSubNav$hdn': '4',
					'CT_Header$ccTopNav$rptNav$ctl03$ccSubNav$hdn': '5',
					'CT_Header$ccTopNav$rptNav$ctl04$ccSubNav$hdn': '6',
					'CT_Header$txtSearch': 'Search Videos',
					'CT_Main_0$txtUsername': username,
					'CT_Main_0$txtPassword': password,
					'CT_Main_0$btnLogin': 'Login',
					'CT_Footer$txtMailingBox': 'Enter Email Address',
					'__EVENTVALIDATION': event_validation,
					'__VIEWSTATE': view_state}

		resp = HTTP.Request(authentication_url, values = values, cacheTime=0).content
		html = HTML.ElementFromString(resp)
		errors = html.xpath('//div[@class="bold red" and contains(text(), "not processed")]/../text()')

		if (len(errors) > 0):
			return False
		else:
			for item in HTTP.CookiesForURL('https://www.hrtv.com/').split(';'):
				if 'ASP.NET_SessionId' in item:
					Dict['ASP.NET_SessionId'] = item
			return True
	else:
		return False

def VideoVault(query='', page = 1):
	loginResult = HRTVLogin()
	Log("Login result: " + str(loginResult))
	
	post_data = dict(SiteId=1, pg=page, searchTerms=query)
	json_data = HTTP.Request(VIDEO_FEED, post_data, cacheTime=0).content
	Log("json_data = " + json_data)

	if (json_data == None) or (json_data == ''):
		return ObjectContainer(header = "No results", message = "No results were found.")

	json = JSON.ObjectFromString(json_data)
	html = HTML.ElementFromString(json["html"])
	videos = html.xpath('//ul/li')

	oc = ObjectContainer()
	
	if page > 1:
		oc.add(DirectoryObject(
			key = Callback(VideoVault, query = query, page = page - 1),
			title = "Previous...",
			thumb = R(ICON_SEARCH)
		))

	for video in videos:
		videoid = video.get('id')[1:]
		title = video.xpath('div[3]/text()')[0]
		thumb = video.xpath('div[1]/a/img')[0].get('src')

		url = 'http://www.hrtv.com/GetVideoPlayerXml.aspx?VideoId=' + videoid
		xml = XML.ElementFromURL(url)
		src = xml.xpath('//src/text()')[0].strip()
		
		match = REGEX_RTMP.match(src)
		if (match == None) or (match.group('rtmp') == None) or (match.group('clip') == None):
			continue
		
		rtmp = match.group('rtmp')
		Log("rtmp = " + rtmp)
		clip = match.group('clip')
		Log("clip = " + clip)
		
		summary = xml.xpath('//desc/text()')[0]

		oc.add(VideoClipObject(
			key = videoid,
			rating_key = videoid,
			title = title,
			summary = summary,
			thumb = thumb,
			items = [
				MediaObject(parts = [
					PartObject(key = RTMPVideoURL(
						url = rtmp,
						clip = clip,
						width = 720,
						height = 450,
						live = False
					))
				])
			]
		))

	oc.add(InputDirectoryObject(
		key = Callback(VideoVault),
		title = "Search",
		thumb = R(ICON_SEARCH),
		prompt = "Search Video Vault"
	))
		
	if page < json["totalPages"]:
		oc.add(DirectoryObject(
			key = Callback(VideoVault, query = query, page = page + 1),
			title = "Next...",
			thumb = R(ICON_SEARCH)
		))

	return oc
	
def ValidatePrefs():
	Dict.Reset()
	HTTP.ClearCookies()