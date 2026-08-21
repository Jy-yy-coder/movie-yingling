# -*- coding: utf-8 -*-
"""
movies_info.csv 离线清洗脚本 —— 按用户 2026-08-04 两轮确认的方案执行:
格式标准化 / 国家语言中英统一 / 占位符清空 / IMDb列改名 / Gemini清占位
删 WikidataID 死列 / 剔信息分<=2 噪声行 / 质量筛选: 有评分全留, 无评分要求资料完整度>=7
源文件不动, 结果覆盖写入 D:/111111111/movies_info_clean.csv (UTF-8 BOM)
"""
import re
import pandas as pd

SRC = r"D:/111111111/movies_info.csv"
DST = r"D:/111111111/movies_info_clean.csv"

df = pd.read_csv(SRC, dtype=str, keep_default_na=False, low_memory=False)
n0 = len(df)

# ---------- 0. 全局 strip ----------
for c in df.columns:
    df[c] = df[c].str.strip().str.replace(r"\s+", " ", regex=True).str.replace("　", "")

# ---------- 1. 占位符统一清空 ----------
PH = {"", "暂无数据", "未知", "不详", "N/A", "n/a", "N/a", "null", "Null", "NULL", "None", "none", "无",
      "-", "——", "—", "暂无简介", "经典电影暂无简介。", "经典电影暂无评价", "暂无"}
EXEMPT = {"movie_id", "片名", "数据来源", "联网补齐来源", "联网补齐时间", "本地补齐来源", "本地补齐时间"}
ph_cnt = 0
for c in df.columns:
    if c in EXEMPT:
        continue
    m = df[c].isin([p for p in PH if p != ""])
    ph_cnt += int(m.sum())
    df.loc[m, c] = ""

# ---------- 2. 上映日期统一为 YYYY-MM-DD 或 YYYY (地区括号信息丢弃) ----------
def norm_date(v):
    if v == "":
        return ""
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", v)
    if m:
        return m.group(1)
    m = re.match(r"^(\d{4})(?:\.0)?$", v)
    if m:
        return m.group(1)
    m = re.match(r"^(\d{4})[(（\-/]", v)
    if m:
        return m.group(1)
    m = re.search(r"(\d{4})", v)
    return m.group(1) if m else ""

d0 = df["上映日期"].copy()
df["上映日期"] = d0.map(norm_date)
date_changed = int((d0 != df["上映日期"]).sum())

# ---------- 3. 年份 0/空 从上映日期回填 ----------
m_back = df["年份"].isin({"0", ""})
backfill = df.loc[m_back, "上映日期"].str.extract(r"(\d{4})", expand=False).fillna("")
df.loc[m_back, "年份"] = backfill
year_fixed = int(m_back.sum() - (df.loc[m_back, "年份"] == "").sum())

# ---------- 4. 片长去空格 "90 分钟" -> "90分钟" (全文替换, 含多段片长) ----------
l0 = df["片长"].copy()
df["片长"] = l0.str.replace(r"(\d)\s+分钟", r"\1分钟", regex=True)
len_changed = int((l0 != df["片长"]).sum())

# ---------- 5. 国家/语言 中英统一 ----------
COUNTRY_MAP = {k.lower(): v for k, v in {
"United States of America":"美国","United States":"美国","USA":"美国","USA USA":"美国","United States USA":"美国","U.S.A.":"美国","U.S.A":"美国","U.S.":"美国","US":"美国","America":"美国","American":"美国","Hawaii":"美国","U.S. Virgin Islands":"美属维尔京群岛","United States Minor Outlying Islands":"美国本土外小岛屿",
"United Kingdom":"英国","UK":"英国","United Kingdom UK":"英国","England":"英国","Britain":"英国","Wales":"英国",
"France":"法国","Frence":"法国","Germany":"德国","German":"德国","DFR":"德国","Federal Republic of Germa":"德国","West Germany":"西德","East Germany":"东德","Eastgermany":"东德","German Democratic Republi":"东德",
"Italy":"意大利","Italian":"意大利","Canada":"加拿大","Canade":"加拿大","Canda":"加拿大","Japan":"日本",
"Russia":"俄罗斯","Russian":"俄罗斯","Russian Federation":"俄罗斯","Russion":"俄罗斯","India":"印度","Indian":"印度","Indai":"印度","Idian":"印度","Indi":"印度","Inida":"印度",
"Sweden":"瑞典","Hong Kong":"中国香港","Australia":"澳大利亚","Austrilia":"澳大利亚","Austira":"澳大利亚","Austrlia":"澳大利亚","Austrialia":"澳大利亚","Australla":"澳大利亚",
"South Korea":"韩国","Korea":"韩国","North Korea":"朝鲜","PRK":"朝鲜","Belgium":"比利时","Beigium":"比利时","Belguim":"比利时","Belgique":"比利时",
"Denmark":"丹麦","Danmark":"丹麦","Demark":"丹麦","Danemark":"丹麦","Finland":"芬兰","Netherlands":"荷兰","The Netherlands":"荷兰","Netherland":"荷兰","Nederland":"荷兰","Netherlandss":"荷兰","Neatherland":"荷兰","Netherlabnds":"荷兰","The Nederlands":"荷兰","Holland":"荷兰","Netherlands Antilles":"荷属安的列斯",
"China":"中国大陆","Mainland China":"中国大陆","Taiwan":"中国台湾","Macao":"中国澳门","Macau":"中国澳门","Tibet":"中国西藏",
"Poland":"波兰","Polan":"波兰","Mexico":"墨西哥","Brazil":"巴西","Brasil":"巴西","Switzerland":"瑞士","Switchland":"瑞士","Argentina":"阿根廷","Argentine":"阿根廷","Agentina":"阿根廷",
"Ireland":"爱尔兰","Irland":"爱尔兰","Austria":"奥地利","Autria":"奥地利","Austra":"奥地利","Czech Republic":"捷克","Czech":"捷克","Chech":"捷克",
"Norway":"挪威","Turkey":"土耳其","Hungary":"匈牙利","Hungry":"匈牙利","Magyarország":"匈牙利","Greece":"希腊","Israel":"以色列","Romania":"罗马尼亚",
"Portugal":"葡萄牙","Purtugal":"葡萄牙","South Africa":"南非","Republic of South Africa":"南非","New Zealand":"新西兰","NewZealand":"新西兰",
"Egypt":"埃及","Egipt":"埃及","Thailand":"泰国","Iran":"伊朗","Serbia":"塞尔维亚","Philippines":"菲律宾","Philippine":"菲律宾","The Philippines":"菲律宾","Philipines":"菲律宾","Philipine":"菲律宾",
"Luxembourg":"卢森堡","Luxeburg":"卢森堡","Croatia":"克罗地亚","Iceland":"冰岛","Chile":"智利","Ukraine":"乌克兰","Ukrain":"乌克兰",
"Estonia":"爱沙尼亚","Bulgaria":"保加利亚","Kazakhstan":"哈萨克斯坦","Soviet Union":"苏联","USSR":"苏联","CCCP":"苏联",
"Singapore":"新加坡","Indonesia":"印度尼西亚","Indonesien":"印度尼西亚","Macedonia":"马其顿","Republic of Macedonia":"马其顿","United Arab Emirates":"阿联酋","UAE":"阿联酋",
"Bosnia and Herzegovina":"波黑","Senegal":"塞内加尔","Sénégal":"塞内加尔","Morocco":"摩洛哥","Maroc":"摩洛哥","Colombia":"哥伦比亚","Columbia":"哥伦比亚",
"Slovenia":"斯洛文尼亚","Peru":"秘鲁","Slovakia":"斯洛伐克","Latvia":"拉脱维亚","Lavtia":"拉脱维亚","Georgia":"格鲁吉亚",
"Uruguay":"乌拉圭","Urguay":"乌拉圭","Venezuela":"委内瑞拉","Ecuador":"厄瓜多尔","Cambodia":"柬埔寨","Pakistan":"巴基斯坦",
"Tunisia":"突尼斯","Lebanon":"黎巴嫩","Burkina Faso":"布基纳法索","Guatemala":"危地马拉","Cameroon":"喀麦隆","Kenya":"肯尼亚","Qatar":"卡塔尔",
"Jamaica":"牙买加","Malaysia":"马来西亚","Algeria":"阿尔及利亚","Syria":"叙利亚","Syrian Arab Republic":"叙利亚",
"Bahamas":"巴哈马","Puerto Rico":"波多黎各","Puerto Rigo":"波多黎各","Purto Rico":"波多黎各",
"Palestine":"巴勒斯坦","Palestinian Territory":"巴勒斯坦","Occupied Palestinian Territory":"巴勒斯坦",
"Bangladesh":"孟加拉国","Mali":"马里","Uganda":"乌干达","Uzbekistan":"乌兹别克斯坦","Jordan":"约旦","Costa Rica":"哥斯达黎加","Mongolia":"蒙古",
"Nepal":"尼泊尔","Czechoslovakia":"捷克斯洛伐克","Československo":"捷克斯洛伐克","Tschechoslowakei":"捷克斯洛伐克",
"Liechtenstein":"列支敦士登","Panama":"巴拿马","Vietnam":"越南","Aruba":"阿鲁巴","Afghanistan":"阿富汗",
"Montenegro":"黑山","Ghana":"加纳","Dominican Republic":"多米尼加","Malta":"马耳他","Iraq":"伊拉克","Namibia":"纳米比亚",
"Yugoslavia":"南斯拉夫","Mauritania":"毛里塔尼亚","Ethiopia":"埃塞俄比亚","Tajikistan":"塔吉克斯坦","Madagascar":"马达加斯加",
"Kyrgyzstan":"吉尔吉斯斯坦","Kyrgyz Republic":"吉尔吉斯斯坦","Albania":"阿尔巴尼亚","Chad":"乍得","Nigeria":"尼日利亚","Haiti":"海地",
"Congo":"刚果","Democratic Republic of Congo":"刚果(金)","The Democratic Republic Of Congo":"刚果(金)","Tanzania":"坦桑尼亚","Honduras":"洪都拉斯",
"Trinidad and Tobago":"特立尼达和多巴哥","Monaco":"摩纳哥","Angola":"安哥拉","Papua New Guinea":"巴布亚新几内亚","Bhutan":"不丹",
"Rwanda":"卢旺达","Paraguay":"巴拉圭","El Salvador":"萨尔瓦多","Nicaragua":"尼加拉瓜","Saudi Arabia":"沙特阿拉伯",
"Ivory Coast":"科特迪瓦","Cote D'Ivoire":"科特迪瓦","Bahrain":"巴林","Niger":"尼日尔","Benin":"贝宁","Myanmar":"缅甸","Burma":"缅甸",
"Sudan":"苏丹","Zimbabwe":"津巴布韦","Botswana":"博茨瓦纳","Guinea":"几内亚","Serbia and Montenegro":"塞尔维亚和黑山",
"Sri Lanka":"斯里兰卡","Liberia":"利比里亚","Gibraltar":"直布罗陀","Moldova":"摩尔多瓦","Lao People's Democratic Republic":"老挝","Laos":"老挝","Somalia":"索马里",
"Mozambique":"莫桑比克","Greenland":"格陵兰","Cyprus":"塞浦路斯","Armenia":"亚美尼亚","Bolivia":"玻利维亚","Belarus":"白俄罗斯","Cuba":"古巴",
"Dominica":"多米尼克","Fiji":"斐济","Grenada":"格林纳达","Samoa":"萨摩亚","French Polynesia":"法属波利尼西亚","Brunei Darussalam":"文莱",
"Turkmenistan":"土库曼斯坦","French Southern Territories":"法属南部领地","Antarctica":"南极洲","French Guiana":"法属圭亚那","Guyana":"圭亚那",
"Martinique":"马提尼克","Barbados":"巴巴多斯","Cayman Islands":"开曼群岛","Bermuda":"百慕大","Montserrat":"蒙特塞拉特","Maldives":"马尔代夫",
"Niue":"纽埃","Western Sahara":"西撒哈拉","Faroe Islands":"法罗群岛","Zaire":"扎伊尔","Togo":"多哥","Gambia":"冈比亚","North Vietnam":"北越",
"Antigua and Barbuda":"安提瓜和巴布达","Saint Vincent and the Grenadines":"圣文森特和格林纳丁斯","Tonga":"汤加","Zambia":"赞比亚","Equatorial Guinea":"赤道几内亚","Kosovo":"科索沃",
"Libyan Arab Jamahiriya":"利比亚","Belize":"伯利兹","Spain":"西班牙","Espana":"西班牙",
"Lithuania":"立陶宛","Lithuanian":"立陶宛","Azerbaijan":"阿塞拜疆","Kuwait":"科威特",
"French":"法国","Polish":"波兰","Danish":"丹麦","Dutch":"荷兰",
"Armania":"亚美尼亚","sverige":"瑞典","NZ":"新西兰","République tchèque":"捷克","Scotland":"英国",
}.items()}

LANG_MAP = {k.lower(): v for k, v in {
"English":"英语","english":"英语","Eng":"英语","EN":"英语","ENG":"英语","English Rap":"英语","English narration":"英语","Dirty English":"英语","Slang English":"英语","GB English":"英语","GB-English":"英语",
"French":"法语","Francais":"法语","anglais":"法语","Spanish":"西班牙语","espana":"西班牙语",
"German":"德语","Deutsch":"德语","Swiss German":"瑞士德语","Swiss-German":"瑞士德语","GermanG":"德语",
"Japanese":"日语","Korean":"韩语","Thai":"泰语","Mandarin":"汉语普通话","Chinese":"汉语普通话","Cantonese":"粤语",
"Hokkien":"闽南语","Min Nan":"闽南语","Southern Min":"闽南语","Hokkian":"闽南语","Taiwanese":"台语","Taiwanese Hokkien":"闽南语",
"Shanghainese":"上海话","Hakka Chinese":"客家话","Teochew":"潮州话","TeoSwa Dialect":"潮州话","Nankinese":"南京话","Nanjingnese":"南京话","Jinyu":"晋语","Yi":"彝语",
"Uyghur":"维吾尔语","Uighurqa":"维吾尔语","Uigur":"维吾尔语","Tibetan":"藏语","Tibetan language":"藏语","Mongolian":"蒙古语","mongolia":"蒙古语","Kazakh":"哈萨克语","kazakh":"哈萨克语","Urumqi":"乌鲁木齐方言","PuTian Dialect":"莆仙话",
"Russian":"俄语","Russiyan":"俄语","Russina":"俄语","Hindi":"印地语","hindi":"印地语","HIndi":"印地语","HINDI":"印地语","Indian":"印地语","Hindu":"印地语","Indi":"印地语",
"Serbian":"塞尔维亚语","Srpski":"塞尔维亚语","Serbo-Croatian":"塞尔维亚-克罗地亚语","Serbo-Croation":"塞尔维亚-克罗地亚语","Bulgarian":"保加利亚语","bulgarian":"保加利亚语",
"Turkish":"土耳其语","Turkic":"土耳其语","Urkish":"土耳其语","Tirkish":"土耳其语","Portuguese":"葡萄牙语","portuguese":"葡萄牙语","Portugese":"葡萄牙语","Purtuguese":"葡萄牙语","Português":"葡萄牙语","Portuguesse":"葡萄牙语",
"Dutch":"荷兰语","dutch":"荷兰语","Nederlands":"荷兰语","Netherlands":"荷兰语","Flemish":"弗拉芒语","Swedish":"瑞典语","swedish":"瑞典语","Svenska":"瑞典语","svanska":"瑞典语","sverige":"瑞典语",
"Danish":"丹麦语","danish":"丹麦语","Dansk":"丹麦语","Denish":"丹麦语","Norwegian":"挪威语","Norsk":"挪威语","Norwagian":"挪威语","Bokmål":"书面挪威语",
"Finnish":"芬兰语","Icelandic":"冰岛语","Íslenska":"冰岛语","Faroese":"法罗语","Italian":"意大利语","italian":"意大利语","ltalian":"意大利语",
"Greek":"希腊语","Polish":"波兰语","polish":"波兰语","Polski":"波兰语","Czech":"捷克语","czech":"捷克语","Československo":"捷克斯洛伐克语",
"Slovak":"斯洛伐克语","slovak":"斯洛伐克语","Slovenčina":"斯洛伐克语","Slovenian":"斯洛文尼亚语","Slovenščina":"斯洛文尼亚语",
"Croatian":"克罗地亚语","croatian":"克罗地亚语","Hrvatski":"克罗地亚语","Bosnian":"波斯尼亚语","Bosanski":"波斯尼亚语",
"Albanian":"阿尔巴尼亚语","shqip":"阿尔巴尼亚语","Macedonian":"马其顿语","Estonian":"爱沙尼亚语","Eesti":"爱沙尼亚语",
"Latvian":"拉脱维亚语","Latviešu":"拉脱维亚语","lettish":"拉脱维亚语","Lietuvi":"立陶宛语","Lithuanian":"立陶宛语","lithuanian":"立陶宛语",
"Ukrainian":"乌克兰语","ukrainian":"乌克兰语","Ukarine":"乌克兰语","Ukraine":"乌克兰语","Belarusian":"白俄罗斯语","belarussian":"白俄罗斯语",
"Hungarian":"匈牙利语","Magyar":"匈牙利语","Magyarország":"匈牙利语","Romanian":"罗马尼亚语","Romany":"罗姆语","Romani":"罗姆语",
"Armenian":"亚美尼亚语","armenian":"亚美尼亚语","Azerbaijani":"阿塞拜疆语","azeri":"阿塞拜疆语","Azerbaijan Language":"阿塞拜疆语","Georgian":"格鲁吉亚语",
"Kyrgyz":"吉尔吉斯语","Kirghiz":"吉尔吉斯语","Tajik":"塔吉克语","Uzbek":"乌兹别克语","uzbek":"乌兹别克语","ozbek":"乌兹别克语","Turkmen":"土库曼语",
"Kurdish":"库尔德语","Persian":"波斯语","persian":"波斯语","Farsi":"波斯语","Pashtu":"普什图语","Pashto":"普什图语","Pushto":"普什图语","Dari":"达里语",
"Arabic":"阿拉伯语","arabic":"阿拉伯语","Arabics":"阿拉伯语","Sudanese Arabic":"苏丹阿拉伯语","Hebrew":"希伯来语","hebrew":"希伯来语","Yiddish":"意第绪语",
"Aramaic":"阿拉姆语","Syriac":"古叙利亚语","Assyrian Neo-Aramaic":"亚述语",
"Telugu":"泰卢固语","telugu":"泰卢固语","Tamil":"泰米尔语","tamil":"泰米尔语","Tamilian":"泰米尔语","Tami":"泰米尔语","Malayalam":"马拉雅拉姆语","malayalam":"马拉雅拉姆语",
"Kannada":"坎纳达语","Knnada":"坎纳达语","Bengali":"孟加拉语","Marathi":"马拉地语","Punjabi":"旁遮普语","Panjabi":"旁遮普语","Gujarati":"古吉拉特语",
"Urdu":"乌尔都语","Sinhala":"僧伽罗语","Sinhalese":"僧伽罗语","Singhalese":"僧伽罗语","Malay":"马来语","Melayu":"马来语","Bahasa Melayu":"马来语","Bahasa Malayu":"马来语","Behasa Melayu":"马来语","Bahasa melayu":"马来语","Malaysian":"马来语",
"Indonesian":"印尼语","indonesian":"印尼语","Bahasa Indonesia":"印尼语","Bahasa indonesia":"印尼语","Indonesien":"印尼语",
"Filipino":"菲律宾语","Tagalog":"他加禄语","Taglog":"他加禄语","Vietnamese":"越南语","vietnamese":"越南语","Tiếng Việt":"越南语","Burmese":"缅甸语",
"Central Khmer":"高棉语","Khmer":"高棉语","Lao":"老挝语","Nepali":"尼泊尔语","Bhojpuri":"博杰普尔语","Manipuri":"曼尼普尔语","Rajasthani":"拉贾斯坦语","Oriya":"奥里亚语","Sindhi":"信德语","Bicolano":"比科尔语","Konkani":"孔卡尼语","Chhattisgarhi":"恰蒂斯加尔语","Beary":"比尔亚语","Visayan":"米沙鄢语",
"Swahili":"斯瓦希里语","Kiswahili":"斯瓦希里语","Suajili":"斯瓦希里语","Zulu":"祖鲁语","zulu":"祖鲁语","isiZulu":"祖鲁语","Xhosa":"科萨语","Somali":"索马里语",
"Amharic":"阿姆哈拉语","Yoruba":"约鲁巴语","Wolof":"沃洛夫语","Hausa":"豪萨语","Ibo":"伊博语","Fula":"富拉语","Fulfulde":"富拉语","Peul":"富拉语",
"Bambara":"班巴拉语","Bamanankan":"班巴拉语","Lingala":"林加拉语","Shona":"修纳语","Kinyarwanda":"卢旺达语","Kirundi":"基隆迪语","Afrikaans":"南非荷兰语","Afrikkans":"南非荷兰语",
"Akan":"阿坎语","Ewe":"埃维语","Fon":"丰语","Dyula":"迪尤拉语","Dioula":"迪尤拉语","Dioulá":"迪尤拉语","Sotho":"塞索托语","SiSwati":"斯瓦蒂语","Tigrigna":"提格利尼亚语",
"Nyanja":"尼昂加语","Bemba":"本巴语","Malagasy":"马达加斯加语","Kriolu":"克里奥尔语","Creole":"克里奥尔语","Kabuverdianu":"佛得角克里奥尔语",
"More":"莫西语","Mooré":"莫西语","Nyaneka":"尼阿内卡语","Soninké":"索宁克语","Sénoufo":"塞努福语","Sonhoy":"桑海语","Songhay":"桑海语","Agni":"阿格尼语","Malinka":"马林凯语",
"Esperanto":"世界语","Latin":"拉丁语","Sanskrit":"梵语","Klingon":"克林贡语","Sindarin":"辛达语","Bable":"巴别语",
"Nahuatl":"纳瓦特尔语","Quechua":"克丘亚语","Aymara":"艾马拉语","Guarani":"瓜拉尼语","Kichwa":"克丘亚语","Maya":"玛雅语","Navajo":"纳瓦霍语","Cherokee":"切罗基语",
"Sioux":"苏族语","Creek":"克里克语","Hopi":"霍皮语","Ojibwa":"奥吉布瓦语","Apache languages":"阿帕切语","Cheyenne":"夏延语","Shoshoni":"肖肖尼语",
"North American Indian":"北美印第安语","Central American Indian l":"中美洲原住民语言","Malecite-Passamaquoddy":"马莱西特-帕萨马科迪语","Washoe":"瓦肖语","Tupi":"图皮语","Karajá":"卡拉雅语","Emberá":"恩贝拉语","Wayu":"瓦尤语","Wayuunaiki":"瓦尤语","Purepecha":"普雷佩查语",
"Inuktitut":"因纽特语","Inupiaq":"因纽皮阿图语","Inuvialuktun":"因纽维卢顿语","Greenlandic":"格陵兰语","Hawaiian":"夏威夷语","native Hawaiian":"夏威夷语",
"Maori":"毛利语","Moari":"毛利语","Cook Islands Māori":"毛利语","Gumatj":"古马奇语","Samoan":"萨摩亚语","Tongan":"汤加语","Fijian":"斐济语","Niuean":"纽埃语","Roviana":"罗维亚纳语","Tonga (Tonga Islands)":"汤加语",
"Basque":"巴斯克语","euskera":"巴斯克语","Catalan":"加泰罗尼亚语","Català":"加泰罗尼亚语","Galician":"加利西亚语","Galego":"加利西亚语","Gallegan":"加利西亚语",
"Welsh":"威尔士语","Cymraeg":"威尔士语","Breton":"布列塔尼语","Gaelic":"盖尔语","Gaeilge":"爱尔兰语","Irish Gaelic":"爱尔兰语","Scots":"苏格兰语",
"Alsatian":"阿尔萨斯语","Sardinian":"撒丁语","Neapolitan":"那不勒斯语","Napolitano":"那不勒斯语","Sicilian":"西西里语","Romansh":"罗曼什语","Luxembourgish":"卢森堡语",
"Eastern Frisian":"东弗里西亚语","Occitan":"奥克语","Saami":"萨米语","Ladino":"拉迪诺语","Ladakhi":"拉达克语",
"Aboriginal":"澳大利亚原住民语言","Ryukyuan":"琉球语","Naxi":"纳西语","Nisga'a":"尼斯加语","Ojihimba":"奥吉赫姆巴语","Hamar":"哈马尔语","Baka":"巴卡语","Khanty":"汉特语","Korowai":"科罗威语","Nushi":"怒苏语","Faliasch":"法利亚语","Kaado":"卡多语","Gunwinggu":"古宁古人语","Kuna":"库纳语","Ndebele":"恩德贝勒语","Kabyle":"卡比尔语",
"Nenets":"涅涅茨语","Tamashek":"塔马舍克语","Dinka":"丁卡语","Masai":"马赛语","Jola-Fonyi":"约拉丰尼语","Serer":"塞雷尔语","Aidoukrou":"艾杜克鲁语",
"Kikuyu":"基库尤语","Aromanian":"阿罗马尼亚语","Yakut":"雅库特语","Kalmyk-Oirat":"卡尔梅克语","Tuvinian":"图瓦语","Ju'hoan":"朱霍安语","Sranan":"斯拉南语","Saramaccan":"萨拉马卡语","Kamassian":"卡马辛语","Atikamekw":"阿提卡梅克语","Pangasinan":"邦阿西楠语","Dzongkha":"宗卡语","Ossetian":"奥塞梯语","Tetun":"德顿语","Tetum":"德顿语","Zomi":"佐米语","Seto language":"塞托语",
"Sign Languages":"手语","French Sign Language":"法国手语","Japanese Sign Language":"日本手语","Russian Sign Language":"俄罗斯手语","American Sign Language":"美国手语","Australian Sign Language":"澳大利亚手语","Icelandic Sign Language":"冰岛手语","Spanish Sign Language":"西班牙手语","Indian Sign Language":"印度手语",
"Silent":"无对白","silent":"无对白","Silence":"无对白","silence":"无对白","Silent Film":"无对白","Slient":"无对白","Silient Movie":"无对白","no dialogue":"无对白","No Dialogue":"无对白","No dialogue None":"无对白","None":"无对白",
"Mexican":"西班牙语","Greek， Ancient (to 1453)":"古希腊语","Polynesian":"波利尼西亚语","Hazaragi":"哈扎拉吉语","Malti":"马耳他语","Maltese":"马耳他语","Mono":"莫诺语",
"조선말":"韩语","עִבְרִית":"希伯来语","فارسی":"波斯语","தமிழ்":"泰米尔语","తెలుగు":"泰卢固语","اردو":"乌尔都语","Український":"乌克兰语","বাংলা":"孟加拉语","ქართული":"格鲁吉亚语","български език":"保加利亚语","ਪੰਜਾਬੀ":"旁遮普语","қазақ":"哈萨克语","پښتو":"普什图语","Berber languages":"柏柏尔语",
"Azərbaycan":"阿塞拜疆语","Chechen":"车臣语","Haitian":"海地语","Tzotzil":"佐齐尔语","Parsee":"帕西语","беларуская мова":"白俄罗斯语","Englis":"英语","Kore":"韩语","Hmong":"苗语","Cree":"克里语","Nama":"纳马语","Mapudungun":"马普切语","Acholi":"阿乔利语","Iloko":"伊洛卡诺语","Athapascan languages":"阿萨巴斯卡语","Badjao":"巴瑶语","many european languages":"",".":"",
}.items()}

JUNK_RE = re.compile(r"(bbc|fox|nbc|sky|atv|channel|电视|official website|website|production|orchestra|ballet|distributor|qew|qwe|gallifrey|worldwide|^9 september|color:|sound mix|usa:\d|uk:\d|hip-hop|^color$|^etc\.?$|phono-kinema|^various$|^n$|david roessell|w\+k)", re.I)
CJK_RUN = re.compile(r"[一-鿿]+")
PAREN = re.compile(r"[（(][^)）]*[)）]")
SUB_C = {k: v for k, v in COUNTRY_MAP.items() if len(k) >= 5}
SUB_L = {k: v for k, v in LANG_MAP.items() if len(k) >= 5}
SUBC_KEYS = sorted(SUB_C, key=len, reverse=True)
SUBL_KEYS = sorted(SUB_L, key=len, reverse=True)

log = {"drop_country": {}, "keep_lang": {}, "drop_lang_country": {}}
def bump(bucket, tok):
    log[bucket][tok] = log[bucket].get(tok, 0) + 1

def substr_hit(keys, sub_map, text):
    for k in keys:
        if re.search(r"\b" + re.escape(k) + r"\b", text):
            return sub_map[k]
    return ""

def clean_cell(cell, kind):
    if cell == "":
        return ""
    MAP = COUNTRY_MAP if kind == "country" else LANG_MAP
    SUBK = SUBC_KEYS if kind == "country" else SUBL_KEYS
    SUBM = SUB_C if kind == "country" else SUB_L
    out = []
    for tok in re.split(r"[/|，、；]+", cell):
        tok = PAREN.sub("", tok).strip().strip("（）() ")
        tok = re.sub(r"\s+", " ", tok).strip()
        if tok == "" or tok in PH:
            continue
        tl = tok.lower()
        cjk = CJK_RUN.findall(tok)
        lat_l = re.sub(r"[一-鿿]+", " ", tok).lower().strip(" .,，")
        v = ""
        if tl in MAP:
            v = MAP[tl]
        elif not cjk:
            if JUNK_RE.search(tok):
                if kind == "country":
                    bump("drop_country", tok)
            elif lat_l in MAP:
                v = MAP[lat_l]
            else:
                v = substr_hit(SUBK, SUBM, tl)
                if not v:
                    if kind == "lang" and lat_l in COUNTRY_MAP:
                        bump("drop_lang_country", tok)
                    elif kind == "country":
                        bump("drop_country", tok)
                    else:
                        bump("keep_lang", tok)
                        v = tok
        else:
            hit = ""
            if lat_l and not JUNK_RE.search(lat_l):
                hit = MAP.get(lat_l) or substr_hit(SUBK, SUBM, lat_l)
            if len(cjk) >= 2:
                out.extend(cjk)
                v = hit if (hit and hit not in cjk) else ""
            else:
                v = hit if hit else cjk[0]
        if v:
            for part in re.split(r"\s*/\s*", v):
                if part and part not in out:
                    out.append(part)
    return " / ".join(out)

before_lat_c = int(df["制片国家/地区"].str.contains(r"[A-Za-z]").sum())
before_lat_l = int(df["语言"].str.contains(r"[A-Za-z]").sum())
df["制片国家/地区"] = df["制片国家/地区"].map(lambda v: clean_cell(v, "country"))
df["语言"] = df["语言"].map(lambda v: clean_cell(v, "lang"))

# ---------- 6. 结构: 删 WikidataID 死列, IMDb 改名, 补 1 行缺失数据来源 ----------
df = df.drop(columns=["WikidataID"]).rename(columns={"IMDb": "IMDb编号"})
df.loc[df["数据来源"] == "", "数据来源"] = "douban_all_data"

# ---------- 7. 行级过滤 (两轮确认口径) ----------
# 第一轮: 剔除信息分<=2 的噪声行(除片名外几乎无信息)
# 第二轮 2026-08-04: 有评分电影全保留(不按分数筛); 无评分电影要求信息分>=7(资料完整够展示)
r = pd.to_numeric(df["豆瓣评分"], errors="coerce")
has_r = (r > 0) & (r <= 10)
score = ((has_r).astype(int)
    + (df["剧情简介"].str.len() > 10).astype(int)
    + (df["海报URL"] != "").astype(int)
    + (df["导演"] != "").astype(int)
    + (df["主演"] != "").astype(int)
    + (df["类型"] != "").astype(int)
    + (df["制片国家/地区"] != "").astype(int)
    + (df["上映日期"].str.len() >= 8).astype(int)
    + (df["IMDb编号"] != "").astype(int)
    + (pd.to_numeric(df["年份"], errors="coerce") > 0).astype(int))
mask_noise = score <= 2
mask_lowinfo = (~mask_noise) & (~has_r) & (score < 7)
n_noise = int(mask_noise.sum())
n_lowinfo = int(mask_lowinfo.sum())
df = df[~(mask_noise | mask_lowinfo)].reset_index(drop=True)

df.to_csv(DST, index=False, encoding="utf-8-sig")

print(f"原始 {n0} 行 -> 输出 {len(df)} 行 (剔噪声 {n_noise} + 无评分资料不全 {n_lowinfo} = 共剔 {n_noise + n_lowinfo} 行), 列数 {len(df.columns)}")
print(f"占位符转空 {ph_cnt} 个单元格 | 上映日期标准化 {date_changed} 行 | 年份回填 {year_fixed} 行 | 片长去空格 {len_changed} 行")
print(f"国家含拉丁字符行: {before_lat_c} -> {int(df['制片国家/地区'].str.contains('[A-Za-z]').sum())}")
print(f"语言含拉丁字符行: {before_lat_l} -> {int(df['语言'].str.contains('[A-Za-z]').sum())}")
print("列:", list(df.columns))
print(f"丢弃的国家词元 {len(log['drop_country'])} 种:", sorted(log["drop_country"].items(), key=lambda x: -x[1]))
print(f"语言列国名丢弃 {len(log['drop_lang_country'])} 种:", sorted(log["drop_lang_country"].items(), key=lambda x: -x[1]))
print(f"语言列原样保留拉丁词元 {len(log['keep_lang'])} 种:", sorted(log["keep_lang"].items(), key=lambda x: -x[1]))
