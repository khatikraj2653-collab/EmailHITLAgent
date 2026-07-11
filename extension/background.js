console.log("HITL Email Agent: background service worker loaded.");

chrome.runtime.onInstalled.addListener(() => {
  console.log("HITL Email Agent installed.");
});
