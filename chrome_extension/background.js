async function get(what, accountName, character) {
  const file = `get-${what}`;
  let response;
  try {
    const params = new URLSearchParams({
      accountName: accountName,
      character: character,
    });
    const url = new URL(
      `https://web.poe.garena.tw/character-window/${file}?${params.toString()}`
    );
    response = await fetch(url);
  } catch (e) {
    throw {
      error: file,
      status: e.toString(),
    };
  }
  if (response.status !== 200) {
    throw {
      error: file,
      status: response.status,
    };
  }
  try {
    return await response.json();
  } catch (e) {
    throw {
      error: file,
      status: e.toString(),
    };
  }
}

async function getContent(sendResponse, accountName, character) {
  let response;
  try {
    response = {
      items: await get("items", accountName, character),
      "passive-skills": await get("passive-skills", accountName, character),
    };
  } catch (e) {
    response = e;
  }
  sendResponse(response);
}

chrome.runtime.onMessageExternal.addListener(function (
  request,
  sender,
  sendResponse
) {
  getContent(sendResponse, request.accountName, request.character);
  return true;
});
