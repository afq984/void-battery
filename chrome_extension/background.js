chrome.runtime.onMessageExternal.addListener(
    function(request, sender, sendResponse) {
        var r = {};
        var completedCount = 0;
        function getX(x) {
            var xhr = new XMLHttpRequest();
            xhr.onreadystatechange = function onReadyStateChange() {
                if (xhr.readyState === XMLHttpRequest.DONE) {
                    if (xhr.status != 200) {
                        if (completedCount != -1) {
                            completedCount = -1;
                            sendResponse({error: "get-" + x, status: xhr.status});
                        }
                    } else {
                        r[x] = JSON.parse(xhr.responseText);
                        completedCount += 1;
                        if (completedCount == 2) {
                            sendResponse(r);
                        }
                    }
                }
            }
            xhr.open("GET", "http://web.poe.garena.tw/character-window/get-" + x + "?accountName=" + encodeURIComponent(request.accountName) + "&character=" + encodeURIComponent(request.character), true);
            xhr.send();
        }
        getX("items");
        getX("passive-skills");
        return true;
    }
);
