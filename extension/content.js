console.log('HITL Email Agent: content script loaded on Gmail.');

const API_BASE = 'http://localhost:8000';

// Inject the spinner animation once
if (!document.getElementById('hitl-spinner-style')) {
  const style = document.createElement('style');
  style.id = 'hitl-spinner-style';
  style.textContent = `
    @keyframes hitl-spin { to { transform: rotate(360deg); } }
    .hitl-spinner {
      width: 18px; height: 18px;
      border: 3px solid #d0d0d0;
      border-top-color: #1a73e8;
      border-radius: 50%;
      animation: hitl-spin 0.7s linear infinite;
      display: inline-block;
      vertical-align: middle;
      margin-right: 8px;
    }
  `;
  document.head.appendChild(style);
}

function showLoadingState(message) {
  const panel = document.getElementById('hitl-decision-panel');
  if (!panel) return;
  panel.textContent = '';

  const row = document.createElement('div');
  Object.assign(row.style, { display: 'flex', alignItems: 'center', padding: '8px 0' });

  const spinner = document.createElement('div');
  spinner.className = 'hitl-spinner';

  const text = document.createElement('div');
  text.textContent = message;
  text.style.fontSize = '13px';
  text.style.color = '#333';

  row.appendChild(spinner);
  row.appendChild(text);
  panel.appendChild(row);
}

function createCheckInboxButton() {
  if (document.getElementById('hitl-check-inbox-btn')) return;

  const checkBtn = document.createElement('button');
  checkBtn.id = 'hitl-check-inbox-btn';
  checkBtn.textContent = '🤖 Check Inbox';
  Object.assign(checkBtn.style, {
    position: 'fixed',
    top: '80px',
    right: '20px',
    zIndex: '9999',
    padding: '10px 16px',
    backgroundColor: '#1a73e8',
    color: 'white',
    border: 'none',
    borderRadius: '20px',
    cursor: 'pointer',
    fontSize: '14px',
    fontFamily: 'Arial, sans-serif',
    boxShadow: '0 2px 6px rgba(0,0,0,0.3)'
  });

  checkBtn.onclick = () => {
    checkBtn.textContent = '⏳ Checking...';
    showCheckingPanel();
    fetch(`${API_BASE}/check-inbox`, { method: 'POST' })
      .then(r => r.json())
      .then(data => {
        console.log('check-inbox result:', data);
        checkBtn.textContent = '🤖 Check Inbox';
        if (data.status === 'awaiting_decision') {
          showDecisionPanel(data);
        } else if (data.status === 'no_new_email') {
          const panel = document.getElementById('hitl-decision-panel');
          if (panel) panel.remove();
          flashButton(checkBtn, 'No new email', '#5f6368');
        }
      })
      .catch(err => {
        console.error('check-inbox error:', err);
        checkBtn.textContent = '❌ Error';
        const panel = document.getElementById('hitl-decision-panel');
        if (panel) panel.remove();
      });
  };

  document.body.appendChild(checkBtn);
}

function showCheckingPanel() {
  const old = document.getElementById('hitl-decision-panel');
  if (old) old.remove();

  const panel = document.createElement('div');
  panel.id = 'hitl-decision-panel';
  Object.assign(panel.style, {
    position: 'fixed', top: '130px', right: '20px', width: '260px',
    backgroundColor: 'white', border: '1px solid #ccc', borderRadius: '12px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.25)', padding: '16px', zIndex: '9999',
    fontFamily: 'Arial, sans-serif', fontSize: '13px'
  });

  document.body.appendChild(panel);
  showLoadingState('Checking inbox...');
}

function flashButton(btn, text, color) {
  const original = btn.textContent;
  const originalColor = btn.style.backgroundColor;
  btn.textContent = text;
  btn.style.backgroundColor = color;
  setTimeout(() => {
    btn.textContent = original;
    btn.style.backgroundColor = originalColor;
  }, 1500);
}

function showDecisionPanel(data) {
  const old = document.getElementById('hitl-decision-panel');
  if (old) old.remove();

  const panel = document.createElement('div');
  panel.id = 'hitl-decision-panel';
  Object.assign(panel.style, {
    position: 'fixed', top: '130px', right: '20px', width: '320px',
    backgroundColor: 'white', border: '1px solid #ccc', borderRadius: '12px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.25)', padding: '16px', zIndex: '9999',
    fontFamily: 'Arial, sans-serif', fontSize: '13px'
  });

  const title = document.createElement('div');
  title.textContent = '📩 New Email Detected';
  title.style.fontWeight = 'bold';
  title.style.marginBottom = '6px';

  const from = document.createElement('div');
  from.textContent = 'From: ' + (data.sender || '');

  const subj = document.createElement('div');
  subj.textContent = 'Subject: ' + (data.subject || '');

  const summaryLabel = document.createElement('div');
  summaryLabel.textContent = 'Summary:';
  summaryLabel.style.fontWeight = 'bold';
  summaryLabel.style.marginTop = '8px';

  const summaryBody = document.createElement('div');
  summaryBody.textContent = data.email_summary || '(no summary available)';
  Object.assign(summaryBody.style, {
    marginTop: '4px', background: '#e8f0fe', padding: '6px', borderRadius: '6px', whiteSpace: 'pre-wrap'
  });

  const bodyLabel = document.createElement('div');
  bodyLabel.textContent = 'Full email:';
  bodyLabel.style.fontWeight = 'bold';
  bodyLabel.style.marginTop = '8px';

  const body = document.createElement('div');
  body.textContent = data.body || '';
  Object.assign(body.style, {
    marginTop: '4px', maxHeight: '80px', overflowY: 'auto',
    background: '#f5f5f5', padding: '6px', borderRadius: '6px', whiteSpace: 'pre-wrap'
  });

  const btnRow = document.createElement('div');
  Object.assign(btnRow.style, { marginTop: '10px', display: 'flex', gap: '6px' });

  const responseBtn = document.createElement('button');
  responseBtn.textContent = 'Response';
  Object.assign(responseBtn.style, { flex: '1', padding: '6px', background: '#34a853', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' });
  responseBtn.onclick = () => sendDecision(data.thread_id, 'response');

  const ignoreBtn = document.createElement('button');
  ignoreBtn.textContent = 'Ignore';
  Object.assign(ignoreBtn.style, { flex: '1', padding: '6px', background: '#ea4335', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' });
  ignoreBtn.onclick = () => sendDecision(data.thread_id, 'ignore');

  btnRow.appendChild(responseBtn);
  btnRow.appendChild(ignoreBtn);

  panel.appendChild(title);
  panel.appendChild(from);
  panel.appendChild(subj);
  panel.appendChild(summaryLabel);
  panel.appendChild(summaryBody);
  panel.appendChild(bodyLabel);
  panel.appendChild(body);
  panel.appendChild(btnRow);

  document.body.appendChild(panel);
}

function showDraftChoicePanel(data) {
  const old = document.getElementById('hitl-decision-panel');
  if (old) old.remove();

  const panel = document.createElement('div');
  panel.id = 'hitl-decision-panel';
  Object.assign(panel.style, {
    position: 'fixed', top: '130px', right: '20px', width: '340px',
    backgroundColor: 'white', border: '1px solid #ccc', borderRadius: '12px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.25)', padding: '16px', zIndex: '9999',
    fontFamily: 'Arial, sans-serif', fontSize: '13px'
  });

  const title = document.createElement('div');
  title.textContent = '✍️ Choose a Draft Reply';
  title.style.fontWeight = 'bold';
  title.style.marginBottom = '6px';

  const history = data.draft_history || [];
  const versionSection = document.createElement('div');

  if (history.length > 1) {
    // --- Version tabs (matches Streamlit's version history behavior) ---
    const tabBar = document.createElement('div');
    Object.assign(tabBar.style, { display: 'flex', gap: '4px', marginTop: '6px', flexWrap: 'wrap' });

    const contentArea = document.createElement('div');
    contentArea.style.marginTop = '6px';

    function renderVersion(h) {
      contentArea.textContent = '';

      const feedbackNote = document.createElement('div');
      feedbackNote.textContent = h.feedback ? `Feedback: ${h.feedback}` : '(original)';
      Object.assign(feedbackNote.style, { fontSize: '11px', color: '#5f6368', marginBottom: '4px', fontStyle: 'italic' });

      const sLabel = document.createElement('div');
      sLabel.textContent = 'Short:';
      sLabel.style.fontWeight = 'bold';

      const sBody = document.createElement('div');
      sBody.textContent = h.short || '';
      Object.assign(sBody.style, { maxHeight: '60px', overflowY: 'auto', background: '#f5f5f5', padding: '6px', borderRadius: '6px', whiteSpace: 'pre-wrap' });

      const lLabel = document.createElement('div');
      lLabel.textContent = 'Long:';
      lLabel.style.fontWeight = 'bold';
      lLabel.style.marginTop = '6px';

      const lBody = document.createElement('div');
      lBody.textContent = h.long || '';
      Object.assign(lBody.style, { maxHeight: '60px', overflowY: 'auto', background: '#f5f5f5', padding: '6px', borderRadius: '6px', whiteSpace: 'pre-wrap' });

      contentArea.appendChild(feedbackNote);
      contentArea.appendChild(sLabel);
      contentArea.appendChild(sBody);
      contentArea.appendChild(lLabel);
      contentArea.appendChild(lBody);
    }

    const tabButtons = [];
    history.forEach((h, idx) => {
      const tabBtn = document.createElement('button');
      tabBtn.textContent = 'v' + h.version;
      Object.assign(tabBtn.style, {
        padding: '4px 10px', fontSize: '12px', border: '1px solid #ccc',
        borderRadius: '14px', cursor: 'pointer', background: '#f1f3f4', color: '#333'
      });
      tabBtn.onclick = () => {
        tabButtons.forEach(b => { b.style.background = '#f1f3f4'; b.style.color = '#333'; });
        tabBtn.style.background = '#1a73e8';
        tabBtn.style.color = 'white';
        renderVersion(h);
      };
      tabButtons.push(tabBtn);
      tabBar.appendChild(tabBtn);
    });

    versionSection.appendChild(tabBar);
    versionSection.appendChild(contentArea);

    // default to latest version
    const latestIdx = history.length - 1;
    tabButtons[latestIdx].click();

    const note = document.createElement('div');
    note.textContent = 'Buttons below always act on the latest version.';
    Object.assign(note.style, { fontSize: '11px', color: '#5f6368', marginTop: '6px' });
    versionSection.appendChild(note);
  } else {
    // --- Single version, no tabs needed ---
    const shortLabel = document.createElement('div');
    shortLabel.textContent = 'Short:';
    shortLabel.style.fontWeight = 'bold';
    shortLabel.style.marginTop = '6px';

    const shortBody = document.createElement('div');
    shortBody.textContent = data.draft_short || '';
    Object.assign(shortBody.style, {
      maxHeight: '60px', overflowY: 'auto', background: '#f5f5f5',
      padding: '6px', borderRadius: '6px', whiteSpace: 'pre-wrap'
    });

    const longLabel = document.createElement('div');
    longLabel.textContent = 'Long:';
    longLabel.style.fontWeight = 'bold';
    longLabel.style.marginTop = '6px';

    const longBody = document.createElement('div');
    longBody.textContent = data.draft_long || '';
    Object.assign(longBody.style, {
      maxHeight: '60px', overflowY: 'auto', background: '#f5f5f5',
      padding: '6px', borderRadius: '6px', whiteSpace: 'pre-wrap'
    });

    versionSection.appendChild(shortLabel);
    versionSection.appendChild(shortBody);
    versionSection.appendChild(longLabel);
    versionSection.appendChild(longBody);
  }

  const btnRow = document.createElement('div');
  Object.assign(btnRow.style, { marginTop: '10px', display: 'flex', gap: '6px' });

  const shortBtn = document.createElement('button');
  shortBtn.textContent = 'Use Short';
  Object.assign(shortBtn.style, { flex: '1', padding: '6px', background: '#1a73e8', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' });
  shortBtn.onclick = () => sendDecision(data.thread_id, 'short');

  const longBtn = document.createElement('button');
  longBtn.textContent = 'Use Long';
  Object.assign(longBtn.style, { flex: '1', padding: '6px', background: '#1a73e8', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' });
  longBtn.onclick = () => sendDecision(data.thread_id, 'long');

  btnRow.appendChild(shortBtn);
  btnRow.appendChild(longBtn);

  const orLabel = document.createElement('div');
  orLabel.textContent = 'Not quite right? Give feedback to regenerate:';
  Object.assign(orLabel.style, { marginTop: '10px', fontSize: '12px', color: '#5f6368' });

  const customRow = document.createElement('div');
  Object.assign(customRow.style, { marginTop: '6px', display: 'flex', gap: '6px' });

  const customInput = document.createElement('input');
  customInput.type = 'text';
  customInput.placeholder = 'e.g. make it more casual';
  Object.assign(customInput.style, {
    flex: '1', padding: '6px', border: '1px solid #ccc', borderRadius: '6px', fontSize: '12px'
  });

  const customBtn = document.createElement('button');
  customBtn.textContent = 'Regenerate';
  Object.assign(customBtn.style, { padding: '6px 10px', background: '#f9ab00', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' });
  customBtn.onclick = () => {
    const text = customInput.value.trim();
    if (!text) return;
    sendDecision(data.thread_id, 'redraft: ' + text);
  };

  customInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') customBtn.click();
  });

  customRow.appendChild(customInput);
  customRow.appendChild(customBtn);

  panel.appendChild(title);
  panel.appendChild(versionSection);
  panel.appendChild(btnRow);
  panel.appendChild(orLabel);
  panel.appendChild(customRow);

  document.body.appendChild(panel);
}

function showResultPanel(result) {
  const panel = document.getElementById('hitl-decision-panel');
  if (!panel) return;
  panel.textContent = '';

  const title = document.createElement('div');
  title.textContent = result.status === 'done' ? '✅ Done' : 'Result';
  title.style.fontWeight = 'bold';
  title.style.marginBottom = '6px';

  const pre = document.createElement('pre');
  pre.style.whiteSpace = 'pre-wrap';
  pre.style.fontSize = '12px';
  pre.textContent = result.summary ? result.summary : JSON.stringify(result, null, 2);

  panel.appendChild(title);
  panel.appendChild(pre);

  // auto-remove after a few seconds
  setTimeout(() => {
    const p = document.getElementById('hitl-decision-panel');
    if (p) p.remove();
  }, 6000);
}

function sendDecision(threadId, decision) {
  let loadingMsg = 'Working...';
  if (decision === 'response') loadingMsg = 'Drafting replies...';
  else if (decision === 'ignore') loadingMsg = 'Ignoring email...';
  else if (decision === 'short' || decision === 'long') loadingMsg = 'Sending...';
  else if (decision.startsWith('redraft:')) loadingMsg = 'Regenerating drafts...';

  showLoadingState(loadingMsg);

  fetch(`${API_BASE}/decide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ thread_id: threadId, decision })
  })
    .then(r => r.json())
    .then(result => {
      console.log('decide result:', result);
      if (result.status === 'awaiting_draft_choice') {
        showDraftChoicePanel(result);
      } else if (result.status === 'awaiting_decision') {
        showDecisionPanel(result);
      } else {
        showResultPanel(result);
      }
    })
    .catch(err => console.error('decide error:', err));
}

createCheckInboxButton();