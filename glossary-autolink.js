/* ============================================================
   白話手冊 · 術語自動連結
   把課文中的專業術語自動變成連到 glossary.html 對應錨點的連結。
   - 同一段落區塊（情境）內，同一個「概念」只連第一次，避免洗版。
   - 跳過標題、公式、既有連結、英文副標等不該動的地方。
   內部「詞 → 錨點」對照表 TERMS 是唯一需要維護的地方。
   ============================================================ */
(function () {
  // 詞 → 白話手冊錨點。長詞排前面，避免「雙工器」被「雙工」搶先比中。
  var TERMS = [
    ['捕獲效應', 'capture'], ['捕捉效應', 'capture'], ['同頻干擾', 'capture'], ['鄰頻干擾', 'capture'],
    ['接收靈敏度', 'gain'], ['靈敏度', 'gain'], ['RF 增益', 'gain'], ['增益', 'gain'],
    ['能量密度', 'psd'], ['功率密度', 'psd'],
    ['調變指數', 'fm'], ['調變', 'fm'], ['載波', 'fm'],
    ['瀑布圖', 'fft'], ['頻譜', 'fft'],
    ['噪聲指數', 'noise'], ['底噪', 'noise'], ['雜訊', 'noise'],
    ['菲涅耳區', 'fresnel'], ['菲涅耳', 'fresnel'],
    ['雙工器', 'duplexer'], ['雙工', 'repeater'], ['中繼台', 'repeater'],
    ['路徑衰減', 'pathloss'], ['自由空間', 'pathloss'],
    ['三角定位', 'df'], ['定向天線', 'df'], ['測向', 'df'],
    ['信號強度', 'rssi'],
    ['視距', 'los'],
    ['過載', 'distortion'], ['失真', 'distortion'],
    ['互調', 'imd'],
    ['寬頻', 'bandwidth'], ['窄頻', 'bandwidth'], ['頻寬', 'bandwidth'],
    ['亞音', 'ctcss'],
    // 英文／縮寫：需大小寫相符且不在英數字中間
    ['CTCSS', 'ctcss'], ['Tone', 'ctcss'],
    ['NBFM', 'fm'], ['NFM', 'fm'], ['FFT', 'fft'], ['FM', 'fm'],
    ['SNR', 'snr'], ['IMD', 'imd'], ['RSSI', 'rssi'],
    ['Friis', 'pathloss'], ['LOS', 'los'], ['Carson', 'bandwidth'],
    ['Overload', 'distortion'], ['Duplexer', 'duplexer'], ['NF', 'noise']
  ];

  var GLOSSARY = 'glossary.html';

  // 找出 term 在 text 中第一個合法位置；英文詞需邊界，回傳 -1 表示沒有。
  function findTerm(text, term) {
    if (/[A-Za-z]/.test(term[0])) {
      var re = new RegExp('(^|[^A-Za-z0-9])' + term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?![A-Za-z0-9])');
      var m = re.exec(text);
      return m ? m.index + m[1].length : -1;
    }
    return text.indexOf(term);
  }

  // 這個文字節點是否該被處理（排除標題/公式/連結/英文副標…）
  function nodeAllowed(node, root) {
    if (!node.nodeValue || !node.nodeValue.trim()) return false;
    var skipTag = { A: 1, BUTTON: 1, SCRIPT: 1, STYLE: 1, CODE: 1, KBD: 1,
                    H1: 1, H2: 1, H3: 1, H4: 1, H5: 1, H6: 1 };
    var skipClass = { 'formula': 1, 'sec-h': 1, 'visual': 1, 'readout': 1, 'en': 1,
                      'eyebrow': 1, 'ct': 1, 'back-btn': 1, 'brand': 1, 'qr-url': 1,
                      'svgfig': 1, 'axis': 1, 'mono': 1 };
    var p = node.parentNode;
    while (p && p !== root && p.nodeType === 1) {
      if (skipTag[p.nodeName]) return false;
      if (p.classList) {
        for (var c = 0; c < p.classList.length; c++) {
          if (skipClass[p.classList[c]]) return false;
        }
      }
      p = p.parentNode;
    }
    return true;
  }

  function processSection(root) {
    var used = {};
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
    var nodes = [];
    while (walker.nextNode()) {
      if (nodeAllowed(walker.currentNode, root)) nodes.push(walker.currentNode);
    }
    nodes.forEach(function (node) {
      // 一個節點可能含多個術語，逐一處理剩餘字串
      for (;;) {
        var best = null;
        for (var i = 0; i < TERMS.length; i++) {
          var term = TERMS[i][0], anchor = TERMS[i][1];
          if (used[anchor]) continue;
          var idx = findTerm(node.nodeValue, term);
          if (idx < 0) continue;
          if (best === null || idx < best.idx ||
              (idx === best.idx && term.length > best.term.length)) {
            best = { idx: idx, term: term, anchor: anchor };
          }
        }
        if (!best) break;
        var matchNode = node.splitText(best.idx);
        var remainder = matchNode.splitText(best.term.length);
        var a = document.createElement('a');
        a.href = GLOSSARY + '#' + best.anchor;
        a.className = 'gterm';
        a.title = '白話手冊：' + best.term;
        a.textContent = best.term;
        matchNode.parentNode.replaceChild(a, matchNode);
        used[best.anchor] = true;
        node = remainder; // 繼續掃剩下的字
      }
    });
  }

  function injectStyle() {
    var css =
      '.gterm{color:inherit;text-decoration:none;border-bottom:1px dashed var(--primary,#F2643C);' +
      'cursor:help;transition:color .15s,border-color .15s;}' +
      '.gterm:hover{color:var(--primary-ink,#B83A1F);border-bottom-style:solid;}';
    var s = document.createElement('style');
    s.textContent = css;
    document.head.appendChild(s);
  }

  function run() {
    injectStyle();
    // 課程頁：每個情境各自一組（同詞在不同情境都會連一次）。
    var sections = document.querySelectorAll('.scenario');
    if (sections.length) {
      sections.forEach(processSection);
    } else {
      // 其他頁（如分組練習、深入數學）：整頁主內容當一個區塊。
      var main = document.querySelector('.wrap') || document.body;
      processSection(main);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
})();
