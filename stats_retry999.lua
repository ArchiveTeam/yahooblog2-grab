-- A simple download counter for Wget.
url_count = 0

wget.callbacks.get_urls = function(file, url, is_css, iri)
  -- progress message
  url_count = url_count + 1
  if url_count % 20 == 0 then
    io.stdout:write("\r - Downloaded "..url_count.." URLs")
    io.stdout:flush()
  end

  return {}
end

wget.callbacks.httploop_result = function(url, err, http_stat)
  if http_stat.statcode == 999 then
    -- try again
    io.stdout:write("\nRate limited. Waiting for 300 seconds...\n")
    io.stdout:flush()
    os.execute("sleep 300")
    return wget.actions.CONTINUE
  else
    return wget.actions.NOTHING
  end
end

