import time
import os
import os.path
import functools
import shutil
import glob
import json
from distutils.version import StrictVersion

from tornado import gen, ioloop
from tornado.httpclient import AsyncHTTPClient, HTTPRequest

import seesaw
from seesaw.project import *
from seesaw.config import *
from seesaw.item import *
from seesaw.task import *
from seesaw.pipeline import *
from seesaw.externalprocess import *
from seesaw.tracker import *


if StrictVersion(seesaw.__version__) < StrictVersion("0.0.10"):
  raise Exception("This pipeline needs seesaw version 0.0.10 or higher.")


USER_AGENT = "Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/533.20.25 (KHTML, like Gecko) Version/5.0.4 Safari/533.20.27"
USER_AGENT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
VERSION = "20130116.01"

class PrepareDirectories(SimpleTask):
  def __init__(self):
    SimpleTask.__init__(self, "PrepareDirectories")

  def process(self, item):
    item_name = item["item_name"]
    dirname = "/".join(( item["data_dir"], item_name ))

    if os.path.isdir(dirname):
      shutil.rmtree(dirname)

    os.makedirs(dirname + "/files")

    item["item_dir"] = dirname
    item["warc_file_base"] = "blog.yahoo.com-%s-%s" % (item_name, time.strftime("%Y%m%d-%H%M%S"))

    open("%(item_dir)s/%(warc_file_base)s.warc.gz" % item, "w").close()

class MoveFiles(SimpleTask):
  def __init__(self):
    SimpleTask.__init__(self, "MoveFiles")

  def process(self, item):
    os.rename("%(item_dir)s/%(warc_file_base)s.warc.gz" % item,
              "%(data_dir)s/%(warc_file_base)s.warc.gz" % item)

    shutil.rmtree("%(item_dir)s" % item)



project = Project(
  title = "Yahoo Blog (Vietnamese)",
  project_html = """
    <img class="project-logo" alt="Yahoo logo" src="http://archiveteam.org/images/thumb/a/a2/Yahoo-logo.png/120px-Yahoo-logo.png" />
    <h2>Yahoo Blogs (Vietnamese) <span class="links"><a href="http://blog.yahoo.com/">Website</a> &middot; <a href="http://tracker.archiveteam.org/yahooblog/">Leaderboard</a></span></h2>
    <p><i>Yahoo</i> might be closing their Vietnamese blogging service.</p>
  """,
  utc_deadline = datetime.datetime(2013,01,13, 23,59,0)
)

pipeline = Pipeline(
  GetItemFromTracker("http://tracker.archiveteam.org/yahooblog", downloader, VERSION),
  PrepareDirectories(),
  WgetDownload([ "./wget-lua",
      "-U", USER_AGENT,
      "-nv",
      "-o", ItemInterpolation("%(item_dir)s/wget.log"),
      "--lua-script", "stats_retry999.lua",
      "--no-check-certificate",
      "--directory-prefix", ItemInterpolation("%(item_dir)s/files"),
      "--force-directories",
      "--adjust-extension",
      "--referer", "http://blog.yahoo.com/explorer/vn",
      "-e", "robots=off",
      "-r", "--level=inf", "--no-remove-listing",
      "--page-requisites", "--span-hosts",
      "--accept-regex", ItemInterpolation(r'http://(blog\.yahoo\.com/%(item_name)s|[^/]+.yimg.com)/|\.(jpg|png|gif|css|js)$'),
      "--reject-regex", '\.wikipedia\.org|[\\\\"\']',
      "--timeout", "60",
      "--tries", "20",
      "--waitretry", "5",
      "--warc-file", ItemInterpolation("%(item_dir)s/%(warc_file_base)s"),
      "--warc-header", "operator: Archive Team",
      "--warc-header", "yahooblog-dld-script-version: " + VERSION,
      "--warc-header", ItemInterpolation("yahooblog-blog: %(item_name)s"),
      ItemInterpolation("http://blog.yahoo.com/%(item_name)s")
    ],
    max_tries = 2,
    accept_on_exit_code = [ 0, 4, 6, 8 ],
  ),
  PrepareStatsForTracker(
    defaults = { "downloader": downloader, "version": VERSION },
    file_groups = {
      "data": [ ItemInterpolation("%(item_dir)s/%(warc_file_base)s.warc.gz") ]
    }
  ),
  MoveFiles(),
  LimitConcurrent(NumberConfigValue(min=1, max=4, default="1", name="shared:rsync_threads", title="Rsync threads", description="The maximum number of concurrent uploads."),
    RsyncUpload(
      target = ConfigInterpolation("fos.textfiles.com::alardland/warrior/yahooblog/%s/", downloader),
#     target = ConfigInterpolation("tracker.archiveteam.org::yahooblog/%s/", downloader),
      target_source_path = ItemInterpolation("%(data_dir)s/"),
      files = [
        ItemInterpolation("%(data_dir)s/%(warc_file_base)s.warc.gz")
      ],
      extra_args = [
        "--recursive",
        "--partial",
        "--partial-dir", ".rsync-tmp"
      ]
    ),
  ),
  SendDoneToTracker(
    tracker_url = "http://tracker.archiveteam.org/yahooblog",
    stats = ItemValue("stats")
  )
)

