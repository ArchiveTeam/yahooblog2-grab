import datetime
from distutils.version import StrictVersion
import os.path
import seesaw
from seesaw.config import NumberConfigValue
from seesaw.externalprocess import WgetDownload
from seesaw.item import ItemInterpolation, ItemValue
from seesaw.pipeline import Pipeline
from seesaw.project import Project
from seesaw.task import SimpleTask, LimitConcurrent
from seesaw.tracker import (GetItemFromTracker, PrepareStatsForTracker,
    UploadWithTracker, SendDoneToTracker)
from seesaw.util import find_executable
import shutil
import time


if StrictVersion(seesaw.__version__) < StrictVersion("0.1.4"):
    raise Exception("This pipeline needs seesaw version 0.1.4 or higher.")

WGET_LUA = find_executable(
    "Wget+Lua",
    ["GNU Wget 1.14.lua.20130523-9a5c"],
    [
        "./wget-lua",
        "./wget-lua-warrior",
        "./wget-lua-local",
        "../wget-lua",
        "../../wget-lua",
        "/home/warrior/wget-lua",
        "/usr/bin/wget-lua"
    ]
)

if not WGET_LUA:
    raise Exception("No usable Wget+Lua found.")


USER_AGENT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
VERSION = "20131217.00"
TRACKER_ID = 'yahooblog'
TRACKER_HOST = 'tracker.archiveteam.org'


class PrepareDirectories(SimpleTask):
    def __init__(self, warc_prefix):
        SimpleTask.__init__(self, "PrepareDirectories")
        self.warc_prefix = warc_prefix

    def process(self, item):
        item_name = item["item_name"]
        dirname = "/".join((item["data_dir"], item_name))

        if os.path.isdir(dirname):
            shutil.rmtree(dirname)

        os.makedirs(dirname)

        item["item_dir"] = dirname
        item["warc_file_base"] = "%s-%s-%s" % (self.warc_prefix, item_name,
            time.strftime("%Y%m%d-%H%M%S"))

        open("%(item_dir)s/%(warc_file_base)s.warc.gz" % item, "w").close()


class MoveFiles(SimpleTask):
    def __init__(self):
        SimpleTask.__init__(self, "MoveFiles")

    def process(self, item):
        os.rename("%(item_dir)s/%(warc_file_base)s.warc.gz" % item,
              "%(data_dir)s/%(warc_file_base)s.warc.gz" % item)

        shutil.rmtree("%(item_dir)s" % item)


wget_args = [
    WGET_LUA,
    "-U", USER_AGENT,
    "-nv",
    "-o", ItemInterpolation("%(item_dir)s/wget.log"),
    "--lua-script", "yahooblog.lua",
    "--output-document", ItemInterpolation("%(item_dir)s/wget.tmp"),
    "--truncate-output",
    "--no-check-certificate",
    "--referer", "http://blog.yahoo.com/explorer/vn",
    "-e", "robots=off",
    "-r", "--level=inf",
    "--page-requisites", "--span-hosts",
    "--accept-regex", ItemInterpolation(r'http://(blog\.yahoo\.com/%(item_name)s|[^/]+.yimg.com)/|\.(jpg|png|gif|css|js)$'),
    "--domains", "yimg.com,blog.yahoo.com",
    "--tries", "20",
    "--waitretry", "3600",
    "--warc-file", ItemInterpolation("%(item_dir)s/%(warc_file_base)s"),
    "--warc-header", "operator: Archive Team",
    "--warc-header", "yahooblog2-dld-script-version: " + VERSION,
    "--warc-header", ItemInterpolation("yahooblog2-name: %(item_name)s"),
    ItemInterpolation("http://blog.yahoo.com/%(item_name)s")
]

if 'bind_address' in globals():
    wget_args.extend(['--bind-address', globals()['bind_address']])
    print('')
    print('*** Wget will bind address at {0} ***'.format(globals()['bind_address']))
    print('')


project = Project(
    title="Yahoo Blog",
    project_html="""
    <img class="project-logo" alt="Yahoo logo" src="http://archiveteam.org/images/thumb/a/a2/Yahoo-logo.png/120px-Yahoo-logo.png" />
    <h2>Yahoo Blogs <span class="links"><a href="http://blog.yahoo.com/">Website</a> &middot; <a href="http://tracker.archiveteam.org/yahooblog/">Leaderboard</a></span></h2>
    <p><i>Yahoo!</i> is a horrible monster.</p>
      """,
    utc_deadline=datetime.datetime(2013, 12, 26, 0, 0, 1)
)

pipeline = Pipeline(
    GetItemFromTracker("http://%s/%s" % (TRACKER_HOST, TRACKER_ID), downloader,
        VERSION),
    PrepareDirectories(warc_prefix='yahooblog'),
    WgetDownload(
        wget_args,
        max_tries=2,
        accept_on_exit_code=[ 0, 8 ],
    ),
    PrepareStatsForTracker(
        defaults={ "downloader": downloader, "version": VERSION },
        file_groups={
            "data": [ ItemInterpolation("%(item_dir)s/%(warc_file_base)s.warc.gz") ]
        }
    ),
    MoveFiles(),
    LimitConcurrent(NumberConfigValue(min=1, max=4, default="1",
        name="shared:rsync_threads", title="Rsync threads",
        description="The maximum number of concurrent uploads."),
        UploadWithTracker(
            "http://%s/%s" % (TRACKER_HOST, TRACKER_ID),
            downloader=downloader,
            version=VERSION,
            files=[
                ItemInterpolation("%(data_dir)s/%(warc_file_base)s.warc.gz")
                ],
            rsync_target_source_path=ItemInterpolation("%(data_dir)s/"),
            rsync_extra_args=[
                "--recursive",
                "--partial",
                "--partial-dir", ".rsync-tmp"
            ]
            ),
    ),
    SendDoneToTracker(
        tracker_url="http://%s/%s" % (TRACKER_HOST, TRACKER_ID),
        stats=ItemValue("stats")
    )
)

