/* ============================================================
   智能反诈骗检测平台 · 前端逻辑
   纯原生 JS（零依赖、零构建）
   ============================================================ */
(function () {
    'use strict';

    /* ---------------- 配置 / 状态 ---------------- */
    var BACKEND = 'http://127.0.0.1:9090';
    var state = {
        token: localStorage.getItem('af_token') || '',
        user: JSON.parse(localStorage.getItem('af_user') || 'null'),
        // GET /api/models 的模型清单缓存（null=未加载）
        modelCatalog: null
    };

    // AI 微服务（Flask 5000）：页面由 5000 托管时同源直连，否则用绝对地址。
    // 指定具体模型做对比测试时走这条链路（Java 9090 不透传 model 参数）。
    var AI_SERVICE = location.port === '5000' ? '' : 'http://127.0.0.1:5000';

    var TITLES = {
        dashboard: '数据仪表盘',
        text: '文本诈骗检测',
        voice: '语音诈骗检测',
        image: '图像诈骗检测',
        fusion: '多模态融合检测',
        records: '检测记录查询'
    };
    var TYPE_LABELS = { text: '文本', voice: '语音', image: '图像', composite: '综合' };

    /* ---------------- DOM 工具 ---------------- */
    function $(sel, ctx) { return (ctx || document).querySelector(sel); }
    function $$(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }
    function el(tag, cls, html) {
        var e = document.createElement(tag);
        if (cls) e.className = cls;
        if (html !== undefined) e.innerHTML = html;
        return e;
    }
    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
    function pad2(n) { return n < 10 ? '0' + n : '' + n; }
    function formatDate(d) {
        d = new Date(d);
        if (isNaN(d.getTime())) return '-';
        return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) +
            ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
    }
    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1024 / 1024).toFixed(2) + ' MB';
    }
    function riskClass(score) { return score >= 70 ? 'high' : (score >= 40 ? 'mid' : 'low'); }
    function levelName(score) { return score >= 70 ? '高风险' : (score >= 40 ? '中风险' : '低风险'); }

    /* ---------------- Toast / Loading ---------------- */
    function toast(msg, type) {
        var box = $('#toast-container');
        var t = el('div', 'toast ' + (type || ''), escapeHtml(msg));
        box.appendChild(t);
        setTimeout(function () {
            t.classList.add('out');
            setTimeout(function () { t.remove(); }, 300);
        }, 2800);
    }
    function showLoading(text) {
        $('#loading-text').textContent = text || '正在处理…';
        $('#global-loading').style.display = 'flex';
    }
    function hideLoading() { $('#global-loading').style.display = 'none'; }

    /* ---------------- API 层 ---------------- */
    // 9090 Spring Boot（需登录 token）
    function apiRequest(method, path, opts) {
        opts = opts || {};
        var headers = opts.headers || {};
        if (state.token) headers['token'] = state.token;
        var fetchOpts = { method: method, headers: headers };
        if (opts.body !== undefined) fetchOpts.body = opts.body;
        return fetch(BACKEND + path, fetchOpts).then(function (resp) {
            return resp.json().catch(function () { return null; }).then(function (json) {
                if (json && json.code === '401') {
                    backToLogin('登录已失效，请重新登录');
                    throw new Error(json.msg || 'unauthorized');
                }
                return { status: resp.status, json: json };
            });
        });
    }
    function apiGet(path) { return apiRequest('GET', path); }
    function apiPost(path, body) {
        return apiRequest('POST', path, {
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
    }
    function apiUpload(path, formData) {
        return apiRequest('POST', path, { body: formData });
    }
    // 5000 Flask（同源，免 token；仅供多模态融合接口使用，常规检测统一走 9090 主链路）
    function aiPost(path, formData) {
        return fetch(path, { method: 'POST', body: formData }).then(function (r) { return r.json(); });
    }
    // 拉取并缓存三模态可用模型清单（Flask 不在线时静默降级，只保留默认主链路）
    var _catalogPromise = null;
    function loadModelCatalog() {
        if (state.modelCatalog) return Promise.resolve(state.modelCatalog);
        if (!_catalogPromise) {
            _catalogPromise = fetch(AI_SERVICE + '/api/models')
                .then(function (r) { return r.json(); })
                .then(function (j) {
                    if (j && j.status === 'ok') { state.modelCatalog = j; }
                    return state.modelCatalog;
                })
                .catch(function () { return null; });
        }
        return _catalogPromise;
    }
    // 用清单填充/刷新一个模型下拉框
    function fillModelSelect(sel, modality) {
        if (!sel) return;
        var cat = state.modelCatalog, group = cat && cat[modality];
        var models = (group && group.models) || [];
        var cur = sel.value;
        var defaultLabel = modality === 'text'
            ? '默认：多模型融合（规则 + ML + BiLSTM + LLM）'
            : '默认：自动选择最佳模型';
        var html = '<option value="">' + defaultLabel + '</option>';
        models.forEach(function (m) {
            var acc = (m.metrics && m.metrics.accuracy != null)
                ? '（测试准确率 ' + (m.metrics.accuracy * 100).toFixed(1) + '%）' : '';
            html += '<option value="' + m.name + '">' + escapeHtml(m.label) + acc + '</option>';
        });
        sel.innerHTML = html;
        if (cur && models.some(function (m) { return m.name === cur; })) sel.value = cur;
    }
    // 渲染模型选择器（下拉 + 提示）；清单到达后自动刷新选项
    function modelPickerHTML(modality, selectId) {
        return '<div class="model-picker">' +
            '<label class="mp-label" for="' + selectId + '">选择检测模型</label>' +
            '<select class="filter-select model-select" id="' + selectId + '">' +
                '<option value="">默认模型（加载清单中…）</option>' +
            '</select>' +
            '<span class="mp-hint">选择具体模型后，检测仍走平台主链路（9090 → 5000），结果同样写入检测记录；默认项使用平台默认模型</span>' +
        '</div>';
    }
    function bindModelPicker(selectId, modality) {
        var sel = document.getElementById(selectId);
        fillModelSelect(sel, modality);
        loadModelCatalog().then(function () { fillModelSelect(sel, modality); });
        return sel;
    }

    /* ---------------- 登录 / 退出 ---------------- */
    function backToLogin(msg) {
        state.token = ''; state.user = null;
        localStorage.removeItem('af_token');
        localStorage.removeItem('af_user');
        $('#app-view').style.display = 'none';
        $('#login-view').style.display = 'flex';
        if (msg) toast(msg, 'warn');
    }

    function bindLogin() {
        var form = $('#login-form');
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var username = $('#login-username').value.trim();
            var password = $('#login-password').value;
            var errBox = $('#login-error');
            errBox.textContent = '';
            if (!username || !password) { errBox.textContent = '请输入用户名和密码'; return; }

            var btn = $('#login-btn');
            btn.disabled = true;
            $('.btn-text', btn).style.display = 'none';
            $('.btn-spinner', btn).style.display = 'inline-block';

            apiPost('/user/login', { username: username, password: password })
                .then(function (r) {
                    var d = r.json;
                    if (d && d.code === '200' && d.data && d.data.token) {
                        state.token = d.data.token;
                        state.user = {
                            id: d.data.id,
                            username: d.data.username,
                            nickname: d.data.nickname
                        };
                        localStorage.setItem('af_token', state.token);
                        localStorage.setItem('af_user', JSON.stringify(state.user));
                        enterApp();
                        toast('登录成功，欢迎回来', 'success');
                    } else {
                        errBox.textContent = (d && d.msg) || '登录失败，请检查账号密码';
                    }
                })
                .catch(function () { errBox.textContent = '无法连接后端服务，请确认 9090 端口已启动'; })
                .finally(function () {
                    btn.disabled = false;
                    $('.btn-text', btn).style.display = 'inline';
                    $('.btn-spinner', btn).style.display = 'none';
                });
        });
    }

    function enterApp() {
        $('#login-view').style.display = 'none';
        $('#app-view').style.display = 'flex';
        var u = state.user || {};
        var name = u.nickname || u.username || '用户';
        $('#user-name').textContent = name;
        $('#user-avatar').textContent = (name[0] || 'A').toUpperCase();
        if (!location.hash || !TITLES[location.hash.replace('#/', '')]) location.hash = '#/dashboard';
        refreshStatus();
    }

    function bindLogout() {
        $('#btn-logout').addEventListener('click', function () {
            apiPost('/user/logout', {}).catch(function () {}).finally(function () {
                backToLogin();
            });
        });
    }

    /* ---------------- 系统状态 ---------------- */
    function refreshStatus() {
        // 9090 健康
        apiGet('/health').then(function (r) {
            var comps = r.json && r.json.data && r.json.data.components;
            var dots = [];
            var mini = $('#health-mini');
            mini.innerHTML = '';
            if (comps) {
                Object.keys(comps).forEach(function (k) {
                    var ok = comps[k] === 'ok';
                    var d = el('span', 'health-dot');
                    d.style.background = ok ? '#22c55e' : '#ef4444';
                    d.title = k + ': ' + comps[k];
                    mini.appendChild(d);
                    dots.push(ok);
                });
                var allOk = dots.every(Boolean);
                $('#svc-dot').className = 'status-dot ' + (allOk ? 'ok' : 'bad');
                $('#svc-text').textContent = allOk ? '全部服务运行正常' : '部分服务异常';
            }
        }).catch(function () {
            $('#svc-dot').className = 'status-dot bad';
            $('#svc-text').textContent = '后端服务不可达';
        });
        $('#health-mini').onclick = function () {
            apiGet('/health').then(function (r) {
                var c = r.json.data.components;
                toast('database:' + c.database + ' / aiService:' + c.aiService + ' / redis:' + c.redis);
            });
        };
    }

    /* ---------------- 路由 ---------------- */
    function router() {
        var route = location.hash.replace('#/', '') || 'dashboard';
        if (!TITLES[route]) route = 'dashboard';

        $$('.menu-item').forEach(function (m) {
            m.classList.toggle('active', m.getAttribute('data-route') === route);
        });
        $('#topbar-title').textContent = TITLES[route];

        var c = $('#content');
        c.innerHTML = '';
        VIEWS[route](c);
    }
    $$('.menu-item').forEach(function (m) {
        m.addEventListener('click', function () {
            location.hash = '#/' + m.getAttribute('data-route');
        });
    });

    /* ---------------- 组件：风险环形图 ---------------- */
    function gaugeHTML(score) {
        var r = 64, cx = 2 * Math.PI * r;
        var offset = cx * (1 - score / 100);
        var color = score >= 70 ? '#dc2626' : (score >= 40 ? '#d97706' : '#16a34a');
        return '' +
            '<div class="gauge-ring">' +
                '<svg width="150" height="150" viewBox="0 0 150 150">' +
                    '<circle cx="75" cy="75" r="' + r + '" fill="none" stroke="#eef2f7" stroke-width="12"/>' +
                    '<circle cx="75" cy="75" r="' + r + '" fill="none" stroke="' + color + '" stroke-width="12" ' +
                        'stroke-linecap="round" stroke-dasharray="' + cx.toFixed(1) + '" stroke-dashoffset="' + offset.toFixed(1) + '"/>' +
                '</svg>' +
                '<div class="gauge-center">' +
                    '<span class="gauge-score" style="color:' + color + '">' + score + '</span>' +
                    '<span class="gauge-unit">风险分</span>' +
                '</div>' +
            '</div>';
    }

    /* ---------------- 组件：检测结果面板 ---------------- */
    function resultPanelHTML(score, rows) {
        var rowsHTML = rows.map(function (r) {
            return '<div class="result-row"><span class="rk">' + escapeHtml(r[0]) +
                '</span><span class="rv">' + r[1] + '</span></div>';
        }).join('');
        return '<div class="result-panel">' +
                    '<div class="risk-gauge">' + gaugeHTML(score) +
                        '<span class="risk-badge ' + riskClass(score) + '">' + levelName(score) + '</span>' +
                    '</div>' +
                    '<div class="result-info">' + rowsHTML + '</div>' +
                '</div>';
    }

    function detailText(d) {
        if (!d) return '-';
        if (typeof d === 'string') return escapeHtml(d);
        return escapeHtml(d.detail || d.risk_level || d.riskLevel || JSON.stringify(d));
    }

    /* ============================================================
       视图：数据仪表盘
       ============================================================ */
    function viewDashboard(c) {
        c.innerHTML =
            '<div class="grid grid-4" id="stat-cards"><div class="empty-tip" style="grid-column:1/-1">数据加载中…</div></div>' +
            '<div class="grid grid-2" style="margin-top:18px">' +
                '<div class="card"><div class="card-header"><span class="card-title">近 7 日检测趋势</span></div><div id="trend-chart"></div></div>' +
                '<div class="card"><div class="card-header"><span class="card-title">风险等级分布</span></div><div id="risk-dist"></div></div>' +
            '</div>' +
            '<div class="card" style="margin-top:18px"><div class="card-header"><span class="card-title">模块使用情况</span></div><div id="module-usage"></div></div>';

        apiGet('/dashboard/stats').then(function (r) {
            var s = r.json.data;
            var cards = [
                ['blue', 'M9 12l2 2 4-4', '累计检测总数', s.totalDetections],
                ['green', 'M12 8v4l3 2', '今日检测', s.todayDetections],
                ['red', 'M12 9v4 M12 17h.01', '高风险记录', s.highRiskCount],
                ['amber', 'M12 2l3 7h7l-5.5 4.5L18 21l-6-4-6 4 1.5-7.5L2 9h7z', '区块链存证', s.totalCerts]
            ];
            $('#stat-cards').innerHTML = cards.map(function (k) {
                return '<div class="stat-card"><div class="stat-icon ' + k[0] + '">' +
                    '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                    '<path d="' + k[1] + '"/></svg></div><div><div class="stat-value">' + k[3] +
                    '</div><div class="stat-label">' + k[2] + '</div></div></div>';
            }).join('');

            // 模块使用
            var mu = s.moduleUsage || {};
            var total = (mu.text || 0) + (mu.voice || 0) + (mu.image || 0) + (mu.composite || 0);
            $('#module-usage').innerHTML = '<div class="modality-bars">' +
                ['text', 'voice', 'image', 'composite'].map(function (t) {
                    var v = mu[t] || 0;
                    var pct = total ? (v / total * 100) : 0;
                    return '<div class="modality-row"><span class="modality-label">' + TYPE_LABELS[t] +
                        '</span><div class="modality-track"><div class="modality-fill" style="width:' + pct + '%"></div></div>' +
                        '<span class="modality-val">' + v + ' 次</span></div>';
                }).join('') + '</div>';
        }).catch(function () {
            $('#stat-cards').innerHTML = '<div class="empty-tip" style="grid-column:1/-1">统计数据加载失败</div>';
        });

        // 趋势图（SVG 折线）
        apiGet('/dashboard/trend').then(function (r) {
            $('#trend-chart').innerHTML = trendSVG(r.json.data);
        });

        // 风险分布
        apiGet('/dashboard/risk-distribution').then(function (r) {
            var dist = r.json.data.distribution;
            var clsMap = { '高风险': 'high', '中风险': 'mid', '低风险': 'low' };
            $('#risk-dist').innerHTML = '<div class="bar-dist">' + dist.map(function (d) {
                var cls = clsMap[d.level];
                return '<div class="bar-dist-row"><span class="bar-dist-label">' + d.level + '</span>' +
                    '<div class="bar-dist-track"><div class="bar-dist-fill ' + cls + '" style="width:' + Math.max(d.ratio, 6) + '%">' +
                    '<span class="bar-dist-count">' + d.count + '</span></div></div>' +
                    '<span class="bar-dist-num">' + d.ratio + '%</span></div>';
            }).join('') + '</div>';
        });
    }

    // SVG 7 日趋势折线图
    function trendSVG(data) {
        var W = 520, H = 210, PL = 38, PR = 16, PT = 18, PB = 34;
        var iw = W - PL - PR, ih = H - PT - PB;
        var max = Math.max(1, Math.max.apply(null, data.map(function (d) { return d.total; })));
        var niceMax = Math.ceil(max / 4) * 4;
        function x(i) { return PL + iw * i / (data.length - 1); }
        function y(v) { return PT + ih * (1 - v / niceMax); }

        var grid = '';
        for (var g = 0; g <= 4; g++) {
            var gy = PT + ih * g / 4, gv = niceMax * (1 - g / 4);
            grid += '<line x1="' + PL + '" y1="' + gy + '" x2="' + W - PR + '" y2="' + gy + '" stroke="#eef2f7"/>' +
                '<text x="' + (PL - 8) + '" y="' + (gy + 4) + '" text-anchor="end" font-size="11" fill="#94a3b8">' + gv + '</text>';
        }
        var pts = data.map(function (d, i) { return x(i) + ',' + y(d.total); }).join(' ');
        var area = 'M' + x(0) + ',' + (PT + ih) + ' L' + data.map(function (d, i) { return x(i) + ',' + y(d.total); }).join(' L') +
            ' L' + x(data.length - 1) + ',' + (PT + ih) + ' Z';
        var dots = data.map(function (d, i) {
            return '<circle cx="' + x(i) + '" cy="' + y(d.total) + '" r="4" fill="#fff" stroke="#1d4ed8" stroke-width="2"/>' +
                '<text x="' + x(i) + '" y="' + (H - 12) + '" text-anchor="middle" font-size="10.5" fill="#94a3b8">' +
                d.date.slice(5) + '</text>';
        }).join('');
        return '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" preserveAspectRatio="xMidYMid meet">' +
            grid +
            '<path d="' + area + '" fill="url(#areaGrad)"/>' +
            '<defs><linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">' +
            '<stop offset="0%" stop-color="#3b82f6" stop-opacity="0.28"/><stop offset="100%" stop-color="#3b82f6" stop-opacity="0.02"/>' +
            '</linearGradient></defs>' +
            '<polyline points="' + pts + '" fill="none" stroke="#1d4ed8" stroke-width="2.5" stroke-linejoin="round"/>' +
            dots + '</svg>';
    }

    /* ============================================================
       视图：文本检测
       ============================================================ */
    var TEXT_SAMPLES = [
        ['中奖', '恭喜您中得我司十周年庆典一等奖，奖金80000元，请先缴纳20%个税，点击链接领取奖金'],
        ['刷单', '亲，足不出户日赚300元，拍下商品给五星好评即可，先垫付小额，完成马上返本金和佣金'],
        ['公检法', '我是北京市公安局民警，你名下银行卡涉嫌诈骗案件，请将资金转入安全清查账户配合调查'],
        ['杀猪盘', '我在一个投资理财平台赚了不少，有内部渠道和老师带单，你也来试试，稳赚不赔'],
        ['贷款', '无抵押无担保，黑户也能秒下款，额度最高50万，加微信即可办理，放款前需交验证金'],
        ['客服退款', '您购买的商品检测出质量问题，现给您双倍退款，请加客服微信，点链接填写银行卡信息'],
        ['冒充领导', '我是你单位王总，这是新号，急需2万元周转，你先转到这个账户，回单位还你'],
        ['注销校园贷', '核查到您大学期间注册过网贷账户，按规定必须注销，否则影响征信，请配合转账操作']
    ];

    function viewText(c) {
        c.innerHTML =
            '<div class="card">' +
                '<div class="card-header"><span class="card-title">输入待检测文本</span></div>' +
                '<textarea class="detect-textarea" id="text-input" placeholder="请输入短信、聊天记录、电话话术等需要检测的文本内容…"></textarea>' +
                '<div class="sample-chips"><span class="chip-label">快捷示例：</span>' +
                    TEXT_SAMPLES.map(function (s, i) {
                        return '<span class="chip" data-i="' + i + '">' + s[0] + '</span>';
                    }).join('') +
                '</div>' +
                modelPickerHTML('text', 'text-model') +
                '<div class="form-actions">' +
                    '<button class="btn-primary" id="text-detect-btn">开始检测</button>' +
                    '<button class="btn-ghost" id="text-clear-btn">清空</button>' +
                '</div>' +
            '</div>' +
            '<div class="card" id="text-result" style="display:none"></div>';

        var ta = $('#text-input');
        var modelSel = bindModelPicker('text-model', 'text');
        $$('.chip', c).forEach(function (chip) {
            chip.addEventListener('click', function () {
                ta.value = TEXT_SAMPLES[+chip.getAttribute('data-i')][1];
                ta.focus();
            });
        });
        $('#text-clear-btn').addEventListener('click', function () {
            ta.value = '';
            $('#text-result').style.display = 'none';
        });
        $('#text-detect-btn').addEventListener('click', function () {
            var content = ta.value.trim();
            if (!content) { toast('请先输入检测文本', 'warn'); return; }
            var btn = $('#text-detect-btn');
            var model = modelSel ? modelSel.value : '';
            btn.disabled = true;
            showLoading(model ? '指定模型分析中…' : 'AI 模型分析中…');

            // 无论是否指定模型，都走平台主链路(9090)：由 Java 透传 model 给 AI 服务并写入检测记录
            var payload = { content: content };
            if (model) payload.model = model;

            apiPost('/detect/text', payload)
                .then(function (r) {
                    var box = $('#text-result');
                    var dd = r.json;
                    if (dd.code !== '200') { toast(dd.msg || '检测失败', 'error'); return; }
                    var info = dd.data;
                    var ai = info.detail || {};
                    box.style.display = 'block';
                    box.innerHTML = '<div class="card-header"><span class="card-title nobar">检测结果</span>' +
                        '<span class="risk-badge ' + riskClass(info.riskScore) + '">记录编号 #' + info.recordId + '</span></div>' +
                        resultPanelHTML(info.riskScore, [
                            ['风险等级', '<b>' + info.riskLevel + '</b>'],
                            (ai.modelLabel ? ['使用模型', escapeHtml(ai.modelLabel)] : null),
                            ['模型详情', detailText(ai)],
                            ['检测内容', escapeHtml(content.length > 120 ? content.slice(0, 120) + '…' : content)]
                        ].filter(Boolean));
                    box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                })
                .catch(function () { toast('请求失败，请确认 9090 主服务与 5000 AI 服务在线', 'error'); })
                .finally(function () { btn.disabled = false; hideLoading(); });
        });
    }

    /* ============================================================
       视图：语音检测
       ============================================================ */
    function viewVoice(c) {
        uploadDetectView(c, {
            modality: 'voice',
            accept: 'audio/*',
            icon: '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/>',
            main: '点击或拖拽语音文件到此处',
            sub: '支持 WAV / MP3 / FLAC 格式，建议使用通话录音',
            endpoint: '/detect/voice',
            preview: function (url) { return '<audio class="audio-preview" controls src="' + url + '"></audio>'; }
        });
    }

    /* ============================================================
       视图：图像检测
       ============================================================ */
    function viewImage(c) {
        uploadDetectView(c, {
            modality: 'image',
            accept: 'image/*',
            icon: '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>',
            main: '点击或拖拽图像文件到此处',
            sub: '支持 JPG / PNG 格式，如聊天截图、诈骗图片、伪造证件照',
            endpoint: '/detect/image',
            preview: function (url) { return '<img src="' + url + '" alt="预览">'; }
        });
    }

    // 上传 + 检测 通用视图（语音/图像共用）
    function uploadDetectView(c, cfg) {
        var picked = null, previewURL = null;
        c.innerHTML =
            '<div class="card">' +
                '<div class="card-header"><span class="card-title">上传待检测文件</span></div>' +
                '<input type="file" id="file-input" accept="' + cfg.accept + '" style="display:none">' +
                '<div class="upload-zone" id="upload-zone">' +
                    '<div class="uz-icon"><svg width="42" height="42" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' + cfg.icon + '</svg></div>' +
                    '<div class="uz-main">' + cfg.main + '</div>' +
                    '<div class="uz-sub">' + cfg.sub + '</div>' +
                '</div>' +
                '<div class="file-preview" id="file-preview"></div>' +
                modelPickerHTML(cfg.modality, 'up-model') +
                '<div class="form-actions">' +
                    '<button class="btn-primary" id="up-detect-btn" disabled>开始检测</button>' +
                '</div>' +
            '</div>' +
            '<div class="card" id="up-result" style="display:none"></div>';

        var modelSel = bindModelPicker('up-model', cfg.modality);
        var input = $('#file-input'), zone = $('#file-input') && $('#upload-zone');
        $('#upload-zone').addEventListener('click', function () { input.click(); });
        input.addEventListener('change', function () {
            if (input.files[0]) pickFile(input.files[0]);
        });
        zone.addEventListener('dragover', function (e) { e.preventDefault(); zone.classList.add('dragover'); });
        zone.addEventListener('dragleave', function () { zone.classList.remove('dragover'); });
        zone.addEventListener('drop', function (e) {
            e.preventDefault();
            zone.classList.remove('dragover');
            if (e.dataTransfer.files[0]) {
                input.files = e.dataTransfer.files;
                pickFile(e.dataTransfer.files[0]);
            }
        });

        function pickFile(f) {
            picked = f;
            if (previewURL) URL.revokeObjectURL(previewURL);
            previewURL = URL.createObjectURL(f);
            var pv = $('#file-preview');
            pv.classList.add('show');
            pv.innerHTML =
                '<div class="file-meta">' +
                    '<span class="fm-name">' + escapeHtml(f.name) + '</span>' +
                    '<span class="fm-size">' + formatSize(f.size) + '</span>' +
                    '<button class="file-clear" id="file-clear" title="移除文件"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>' +
                '</div>' +
                cfg.preview(previewURL);
            $('#file-clear').addEventListener('click', clearFile);
            $('#up-detect-btn').disabled = false;
        }
        function clearFile() {
            picked = null;
            if (previewURL) { URL.revokeObjectURL(previewURL); previewURL = null; }
            input.value = '';
            $('#file-preview').classList.remove('show');
            $('#file-preview').innerHTML = '';
            $('#up-detect-btn').disabled = true;
            $('#up-result').style.display = 'none';
        }

        $('#up-detect-btn').addEventListener('click', function () {
            if (!picked) return;
            var btn = $('#up-detect-btn');
            var model = modelSel ? modelSel.value : '';
            btn.disabled = true;
            showLoading(model ? '指定模型分析中…' : 'AI 模型分析中…');
            var fd = new FormData();
            fd.append('file', picked);
            if (model) fd.append('model', model);

            // 始终走平台主链路(9090)：Java 透传 model 给 AI 服务，检测结果写入检测记录
            apiUpload(cfg.endpoint, fd)
                .then(function (r) {
                    var box = $('#up-result');
                    var dd = r.json;
                    if (dd.code !== '200') { toast(dd.msg || '检测失败', 'error'); return; }
                    var info = dd.data, ai = info.detail || {};
                    box.style.display = 'block';
                    box.innerHTML = '<div class="card-header"><span class="card-title nobar">检测结果</span>' +
                        '<span class="risk-badge ' + riskClass(info.riskScore) + '">记录编号 #' + info.recordId + '</span></div>' +
                        resultPanelHTML(info.riskScore, [
                            ['风险等级', '<b>' + info.riskLevel + '</b>'],
                            (ai.modelLabel ? ['使用模型', escapeHtml(ai.modelLabel)] : null),
                            ['模型详情', detailText(ai)],
                            ['文件名称', escapeHtml(picked.name)]
                        ].filter(Boolean));
                    box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                })
                .catch(function () { toast('请求失败，请确认 9090 主服务与 5000 AI 服务在线', 'error'); })
                .finally(function () { btn.disabled = false; hideLoading(); });
        });
    }

    /* ============================================================
       视图：多模态融合检测
       ============================================================ */
    function viewFusion(c) {
        var voiceFile = null, imageFile = null, voiceURL = null, imageURL = null;
        c.innerHTML =
            '<div class="card">' +
                '<div class="card-header"><span class="card-title">同一案例的三种证据输入</span>' +
                    '<span style="font-size:12px;color:#94a3b8">由多模态晚期融合模型（Stacking）综合判定</span></div>' +
                '<div class="form-item"><label>① 文本内容（短信/聊天记录）</label>' +
                    '<textarea class="detect-textarea" id="fu-text" style="min-height:90px" placeholder="请输入文本证据…"></textarea></div>' +

                '<div class="grid grid-2">' +
                    '<div class="form-item"><label>② 语音证据（通话录音）</label>' +
                        '<input type="file" id="fu-voice" accept="audio/*" style="display:none">' +
                        '<div class="upload-zone" id="fu-voice-zone" style="padding:22px">' +
                            '<div class="uz-main">选择语音文件</div><div class="uz-sub">WAV / MP3</div></div>' +
                        '<div id="fu-voice-pv"></div></div>' +
                    '<div class="form-item"><label>③ 图像证据（截图/图片）</label>' +
                        '<input type="file" id="fu-image" accept="image/*" style="display:none">' +
                        '<div class="upload-zone" id="fu-image-zone" style="padding:22px">' +
                            '<div class="uz-main">选择图像文件</div><div class="uz-sub">JPG / PNG</div></div>' +
                        '<div id="fu-image-pv"></div></div>' +
                '</div>' +
                '<div class="form-actions">' +
                    '<button class="btn-primary" id="fu-run-btn">融合检测</button>' +
                    '<button class="btn-ghost" id="fu-sample-btn">填入诈骗示例</button>' +
                '</div>' +
            '</div>' +
            '<div class="card" id="fu-result" style="display:none"></div>';

        function miniPicker(zoneId, inputId, pvId, isImage) {
            var zone = $('#' + zoneId), input = $('#' + inputId), pv = $('#' + pvId);
            zone.addEventListener('click', function () { input.click(); });
            input.addEventListener('change', function () {
                var f = input.files[0];
                if (!f) return;
                if (isImage) { imageFile = f; } else { voiceFile = f; }
                var u = URL.createObjectURL(f);
                if (isImage && imageURL) URL.revokeObjectURL(imageURL);
                if (!isImage && voiceURL) URL.revokeObjectURL(voiceURL);
                if (isImage) imageURL = u; else voiceURL = u;
                pv.innerHTML = '<div class="file-meta"><span class="fm-name">' + escapeHtml(f.name) +
                    '</span><span class="fm-size">' + formatSize(f.size) + '</span></div>' +
                    (isImage ? '<img src="' + u + '" style="max-height:200px;margin-top:8px;border-radius:9px;width:100%">' :
                        '<audio controls src="' + u + '" style="width:100%;margin-top:8px"></audio>');
            });
        }
        miniPicker('fu-voice-zone', 'fu-voice', 'fu-voice-pv', false);
        miniPicker('fu-image-zone', 'fu-image', 'fu-image-pv', true);

        $('#fu-sample-btn').addEventListener('click', function () {
            $('#fu-text').value = '您好，这里是公安局，你的银行账户涉嫌一起洗钱案件，请把存款转入我们的安全监管账户接受调查';
            var casesDir = null;
            toast('文本已填入示例，语音和图像请从数据目录选择', 'info');
        });

        $('#fu-run-btn').addEventListener('click', function () {
            var text = $('#fu-text').value.trim();
            if (!text) { toast('请输入文本内容', 'warn'); return; }
            if (!voiceFile) { toast('请选择语音证据文件', 'warn'); return; }
            if (!imageFile) { toast('请选择图像证据文件', 'warn'); return; }

            var btn = $('#fu-run-btn');
            btn.disabled = true;
            showLoading('多模态融合分析中…');
            var fd = new FormData();
            fd.append('text', text);
            fd.append('voice', voiceFile);
            fd.append('image', imageFile);
            aiPost('/api/assess/risk-multimodal', fd)
                .then(function (d) {
                    if (d.error || d.fallback) { toast(d.detail || d.error || '融合检测失败', 'error'); return; }
                    var ms = d.modalityScores || {}, mp = d.modalityProbability || {};
                    var rows = [
                        ['判定结论', '<b>' + (d.isFraud ? '诈骗' : '正常') + '</b>　置信度 ' + (d.confidence != null ? (d.confidence * 100).toFixed(1) + '%' : '-')],
                        ['融合策略', escapeHtml(d.strategy || '-')],
                        ['文本模态', '风险分 ' + (ms.text != null ? ms.text : '-') + '　诈骗概率 ' + (mp.text != null ? (mp.text * 100).toFixed(1) + '%' : '-')],
                        ['语音模态', '风险分 ' + (ms.voice != null ? ms.voice : '-') + '　诈骗概率 ' + (mp.voice != null ? (mp.voice * 100).toFixed(1) + '%' : '-')],
                        ['图像模态', '风险分 ' + (ms.image != null ? ms.image : '-') + '　诈骗概率 ' + (mp.image != null ? (mp.image * 100).toFixed(1) + '%' : '-')],
                        ['模型说明', escapeHtml(d.detail || '-')]
                    ];
                    var box = $('#fu-result');
                    box.style.display = 'block';
                    box.innerHTML = '<div class="card-header"><span class="card-title nobar">融合检测结果</span></div>' +
                        resultPanelHTML(d.riskScore, rows);
                    box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                })
                .catch(function () { toast('融合服务调用失败，请确认 5000 端口在线', 'error'); })
                .finally(function () { btn.disabled = false; hideLoading(); });
        });
    }

    /* ============================================================
       视图：检测记录
       ============================================================ */
    function viewRecords(c) {
        var pageNum = 1, pageSize = 10, filterType = '';
        c.innerHTML =
            '<div class="card">' +
                '<div class="card-header"><span class="card-title">检测历史记录</span>' +
                    '<div class="filter-bar">' +
                        '<select class="filter-select" id="rec-filter">' +
                            '<option value="">全部类型</option>' +
                            '<option value="text">文本</option>' +
                            '<option value="voice">语音</option>' +
                            '<option value="image">图像</option>' +
                            '<option value="composite">综合</option>' +
                        '</select>' +
                    '</div>' +
                '</div>' +
                '<div class="table-wrap"><table class="data-table">' +
                    '<thead><tr><th>编号</th><th>类型</th><th>检测内容</th><th>风险分</th><th>等级</th><th>检测时间</th></tr></thead>' +
                    '<tbody id="rec-tbody"></tbody>' +
                '</table></div>' +
                '<div class="pagination" id="rec-pagination"></div>' +
            '</div>';

        $('#rec-filter').addEventListener('change', function () {
            filterType = this.value;
            pageNum = 1;
            load();
        });
        load();

        function load() {
            var tbody = $('#rec-tbody');
            tbody.innerHTML = '<tr><td colspan="6"><div class="empty-tip">加载中…</div></td></tr>';
            var qs = '?pageNum=' + pageNum + '&pageSize=' + pageSize + (filterType ? '&type=' + filterType : '');
            apiGet('/detect/records' + qs).then(function (r) {
                var p = r.json.data;
                if (!p.records.length) {
                    tbody.innerHTML = '<tr><td colspan="6"><div class="empty-tip">暂无检测记录</div></td></tr>';
                } else {
                    tbody.innerHTML = p.records.map(function (rec) {
                        return '<tr><td>#' + rec.id + '</td>' +
                            '<td><span class="type-tag ' + rec.type + '">' + (TYPE_LABELS[rec.type] || rec.type) + '</span></td>' +
                            '<td><div class="cell-content" title="' + escapeHtml(rec.inputContent) + '">' + escapeHtml(rec.inputContent) + '</div></td>' +
                            '<td><span class="score-pill ' + riskClass(rec.riskScore) + '">' + rec.riskScore + '</span></td>' +
                            '<td>' + rec.riskLevel + '</td>' +
                            '<td>' + formatDate(rec.createTime) + '</td></tr>';
                    }).join('');
                }
                renderPagination(p);
            });
        }

        function renderPagination(p) {
            var pg = $('#rec-pagination');
            var pages = p.pages || 1;
            var html = '<span class="page-info">共 ' + p.total + ' 条，第 ' + p.current + '/' + pages + ' 页</span>';
            html += '<button class="page-btn" data-go="prev"' + (pageNum <= 1 ? ' disabled' : '') + '>上一页</button>';

            var start = Math.max(1, Math.min(pageNum - 2, pages - 4));
            var end = Math.min(pages, start + 4);
            for (var i = start; i <= end; i++) {
                html += '<button class="page-btn ' + (i === pageNum ? 'active' : '') + '" data-go="' + i + '">' + i + '</button>';
            }
            html += '<button class="page-btn" data-go="next"' + (pageNum >= pages ? ' disabled' : '') + '>下一页</button>';
            pg.innerHTML = html;
            $$('.page-btn', pg).forEach(function (b) {
                b.addEventListener('click', function () {
                    var go = b.getAttribute('data-go');
                    if (go === 'prev') pageNum--;
                    else if (go === 'next') pageNum++;
                    else pageNum = +go;
                    load();
                });
            });
        }
    }

    var VIEWS = {
        dashboard: viewDashboard,
        text: viewText,
        voice: viewVoice,
        image: viewImage,
        fusion: viewFusion,
        records: viewRecords
    };

    /* ---------------- 启动 ---------------- */
    window.addEventListener('hashchange', router);

    bindLogin();
    bindLogout();

    if (state.token) {
        enterApp();
        router();
    } else {
        $('#login-view').style.display = 'flex';
    }
    setInterval(function () { if (state.token) refreshStatus(); }, 30000);

})();
