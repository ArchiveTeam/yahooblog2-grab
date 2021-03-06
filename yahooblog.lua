-- A simple download counter for Wget.
url_count = 0

wget.callbacks.get_urls = function(file, url, is_css, iri)
  -- progress message
  url_count = url_count + 1
  if url_count % 2 == 0 then
    io.stdout:write("\r - Downloaded "..url_count.." URLs.")
    io.stdout:flush()
  end

  return {}
end

wget.callbacks.download_child_p = function(urlpos, parent, depth, start_url_parsed, iri, verdict, reason)
  local url = urlpos["url"]["url"]
  if string.match(url, "/abuse%?") then
    return false
  end

  -- don't go chasin' waterfalls
  if string.match(url, "http:%%5C/%%5C/blog%.yahoo%.com") then
    return false
  end

  if string.match(url, "\\") then
    return false
  end

  -- don't get all kinds of redundant content that we don't have time for
  if string.match(url, "/tag/") then
    return false
  end

  if string.match(url, "/date/") then
    return false
  end

  if string.match(url, "/category/") then
    return false
  end

  if string.match(url, "/uncategorized") then
    return false
  end

  if string.match(url, "%?compact") then
    return false
  end

  -- already in wayback machine
  if string.match(url, "cosmos%.bcst%.yahoo%.com/player/media/swf/FLVVideoSolo%.swf") then
    return false
  end

  return verdict
end


-- The number of times we'll retry requests with code >= 500 and <= 599.
-- If this hits zero, we skip the URL, reset the counter, and go to the next
-- one.
local retry_counter = 5

wget.callbacks.httploop_result = function(url, err, http_stat)
  local sleep_time = 60
  local status_code = http_stat["statcode"]

  if status_code >= 500 then
    -- issue #2, skip broken rss feed
    if status_code == 500 and string.match(url["url"], "/rss") then
      io.stdout:write("(rss skip)\n")
      io.stdout:flush()
      return wget.actions.EXIT
    end

    if status_code <= 599 then
      retry_counter = retry_counter - 1
    end

    if retry_counter <= 0 then
      io.stdout:write("Skipping "..url["url"].." due to too many failures.\n")
      io.stdout:flush()
      retry_counter = 5
      return wget.actions.EXIT
    else
      io.stdout:write("\nYahoo!!! (code "..http_stat.statcode.."). Sleeping for ".. sleep_time .." seconds.  Will retry "..retry_counter.." more times.\n")
      io.stdout:flush()

      -- Note that wget has its own linear backoff to this time as well
      os.execute("sleep " .. sleep_time)
      return wget.actions.CONTINUE
    end
  else
    -- We're okay; sleep a bit (if we have to) and continue
    local sleep_time = 0.1 * (math.random(75, 125) / 100.0)

    if string.match(url["url"], "yimg%.com") then
      -- We should be able to go fast on images since that's what a web browser does
      sleep_time = 0
    end

    if sleep_time > 0.001 then
      os.execute("sleep " .. sleep_time)
    end

    tries = 0
    return wget.actions.NOTHING
  end
end

wget.callbacks.lookup_host = function(host)
  if string.match(host, "blog%.yahoo%.com") then
    local table = {"66.196.66.157", "66.196.66.156", "66.196.66.212", "66.196.66.213"}
    return table[ math.random( #table ) ]
  else
    -- use normal DNS ip
    return nil
  end
end
