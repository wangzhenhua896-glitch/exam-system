/**
 * 自动解析模块 — 将粘贴的整段文本解析为题目表单字段
 * 通过 window.AutoParse 暴露，非 ES Module，供 question-edit.html 等页面调用
 */
(function() {
    'use strict';

    /**
     * 英文题解析
     * @param {string} fullText - 粘贴的完整文本
     * @returns {{ content, score, standardAnswer, rubricRules, rubricPoints, aiRubric, parseResult }}
     */
    function parseEnglish(fullText) {
        let questionContent = '';
        let answerContent = '';
        let rubricContent = '';
        let extractedMaxScore = null;
        const scoreRegex = /[（\(](\d+\.?\d*)\s*(分|points?|marks?)[）\)]/i;
        const scoreMatch2 = fullText.match(scoreRegex);
        if (scoreMatch2) extractedMaxScore = parseFloat(scoreMatch2[1]);
        const rubricDividerRegex = /(请严格按照以下规则对学生答案进行评分|Grade strictly based on the following scoring criteria|Scoring Rules|Grading Criteria)[：:]?\s*/i;
        const rubricMatch = rubricDividerRegex.exec(fullText);
        if (rubricMatch) {
            questionContent = fullText.slice(0, rubricMatch.index).trim();
            rubricContent = fullText.slice(rubricMatch.index + rubricMatch[0].length).trim();
        } else {
            questionContent = fullText;
        }
        questionContent = questionContent.replace(/[（\(]\d+\.?\d*\s*(分|points?|marks?)[）\)]/gi, '').trim();
        if (rubricContent) {
            const answerLines = [];
            const answerExtractRegex = /(参考答案|Answer|Reference Answer|Model Answer|Expected Answer)[：:]\s*(.+)/gi;
            let m;
            while ((m = answerExtractRegex.exec(rubricContent)) !== null) {
                const line = m[2].trim();
                if (line) answerLines.push(line);
            }
            if (answerLines.length > 0) {
                answerContent = answerLines.map((a, i) => `${i + 1}. ${a}`).join('\n');
            }
        }
        const pointLines = [];
        if (rubricContent) {
            const pointRegex = /(得分点\s*\d+|Scoring\s*[Pp]oint\s*\d+|Criterion\s*\d+|Point\s*\d+)[：:]\s*(.+)/gi;
            let pm;
            while ((pm = pointRegex.exec(rubricContent)) !== null) {
                pointLines.push(pm[0].trim());
            }
            if (pointLines.length === 0) {
                const lines = rubricContent.split('\n');
                for (const line of lines) {
                    const t = line.trim();
                    if (/^\d+[\.\、]/.test(t) && /[（\(]\d+\.?\d*\s*(分|points?|marks?)[）\)]/i.test(t)) {
                        pointLines.push(t);
                    }
                }
            }
            if (pointLines.length === 0) {
                const lines = rubricContent.split('\n');
                for (const line of lines) {
                    const t = line.trim();
                    if (/^\([a-zA-Z]\)/.test(t)) {
                        pointLines.push(t);
                    }
                }
            }
        }
        const result = {
            content: questionContent || '',
            score: (extractedMaxScore && !isNaN(extractedMaxScore)) ? extractedMaxScore : null,
            standardAnswer: answerContent || '',
            rubricRules: rubricContent || '',
            rubricPoints: pointLines.length > 0 ? pointLines.join('\n') : '',
            aiRubric: 'Grade strictly based on the scoring criteria. Each point is scored independently. Partial credit applies for partially correct answers. Total score must not exceed the maximum.',
            parseResult: {
                maxScore: extractedMaxScore || null,
                points: pointLines.length,
                hasAnswer: !!answerContent
            }
        };
        return result;
    }

    /**
     * 中文题解析
     * @param {string} fullText - 粘贴的完整文本
     * @returns {{ content, score, standardAnswer, rubricRules, rubricPoints, aiRubric, parseResult }}
     */
    function parseChinese(fullText) {
        let questionContent = '';
        let answerContent = '';
        let rubricContent = '';
        let aiPromptContent = '';
        let extractedMaxScore = null;
        const questionRegex = /(题目内容|命题示例)[：:]\s*/i;
        const answerRegex = /(标准答案|参考答案|参考解答|标准解答)[：:]\s*/i;
        const rubricRegex = /(评分标准|评分总则|评分规则|得分要点|给分标准|人工评分|人工规则|给分规则)[：:]\s*/i;
        const aiRegex = /(AI评分提示|AI提示|AI评分|AI规则)[：:]\s*/i;
        const scoreRegex = /(满分|总分|分值)[：:\s]*(\d+\.?\d*)/i;
        const parenScoreRegex = /[（\(](\d+\.?\d*)分[）\)]/;
        let currentSection = 'question';
        let text = fullText;
        while (text.length > 0) {
            let found = false, earliestPos = Infinity, foundRegex = null, foundMatch = null;
            const checkMatch = (regex) => {
                const match = regex.exec(text);
                if (match && match.index < earliestPos) { earliestPos = match.index; foundRegex = regex; foundMatch = match; found = true; }
            };
            checkMatch(answerRegex); checkMatch(rubricRegex); checkMatch(aiRegex); checkMatch(questionRegex);
            if (found) {
                const before = text.slice(0, earliestPos).trim();
                if (before) {
                    if (currentSection === 'question') questionContent += before + '\n';
                    else if (currentSection === 'answer') answerContent += before + '\n';
                    else if (currentSection === 'rubric') rubricContent += before + '\n';
                    else if (currentSection === 'ai') aiPromptContent += before + '\n';
                }
                if (foundRegex === answerRegex) currentSection = 'answer';
                else if (foundRegex === rubricRegex) currentSection = 'rubric';
                else if (foundRegex === aiRegex) currentSection = 'ai';
                else if (foundRegex === questionRegex) currentSection = 'question';
                text = text.slice(foundMatch.index + foundMatch[0].length);
            } else {
                if (text.trim()) {
                    if (currentSection === 'question') questionContent += text.trim() + '\n';
                    else if (currentSection === 'answer') answerContent += text.trim() + '\n';
                    else if (currentSection === 'rubric') rubricContent += text.trim() + '\n';
                    else if (currentSection === 'ai') aiPromptContent += text.trim() + '\n';
                }
                break;
            }
        }
        const scoreMatch = fullText.match(scoreRegex);
        if (scoreMatch) extractedMaxScore = parseFloat(scoreMatch[2]);
        if (!extractedMaxScore) { const pm = fullText.match(parenScoreRegex); if (pm) extractedMaxScore = parseFloat(pm[1]); }

        let content = questionContent.trim();
        let score = (extractedMaxScore && !isNaN(extractedMaxScore)) ? extractedMaxScore : null;
        let standardAnswer = answerContent.trim();
        let rubricRules = '';
        let rubricPoints = '';

        // 从标准答案中提取得分点
        if (standardAnswer) {
            let answerText = standardAnswer;
            const segments = answerText.split(/(?:；\s*(?=\d+[、\.])|\n\s*(?=\d+[、\.]))/);
            const parts = segments.length > 1 ? segments : answerText.split(/[；;]\s*/);
            let extractedPoints = '', extractedCount = 0;
            for (const part of parts) {
                const tp = part.trim();
                if (!tp) continue;
                const ruleMatch = tp.match(/(.*?)([（(][^)）]*分[^)）]*[)）])/);
                if (ruleMatch) {
                    let c = ruleMatch[1].trim();
                    c = c.replace(/^\d+[、\.]\s*/, '').replace(/^[一二三四五六七八九十]+、\s*/, '');
                    if (c) {
                        const sm = ruleMatch[2].match(/(\d+\.?\d*)\s*分/);
                        if (sm) c += ` (${sm[1]}分)`;
                        extractedPoints += c + '\n'; extractedCount++;
                    }
                } else if (tp.match(/^\d+[、\.]/) && (tp.includes('分）') || tp.includes('分)'))) {
                    let processed = tp.replace(/^\d+[、\.]\s*/, '');
                    processed = processed.replace(/（\s*(\d+\.?\d*)\s*分[^）]*）/g, '($1分)');
                    processed = processed.replace(/\(\s*(\d+\.?\d*)\s*分[^\)]*\)/g, '($1分)');
                    if (processed.trim()) { extractedPoints += processed + '\n'; extractedCount++; }
                } else {
                    const cleaned = tp.replace(/^\d+[、\.]\s*/, '').replace(/^[一二三四五六七八九十]+、\s*/, '');
                    if (cleaned.trim()) { extractedPoints += cleaned + '\n'; extractedCount++; }
                }
            }
            if (extractedCount >= 1) rubricPoints = extractedPoints.trim();
        }

        // 从评分标准中提取规则和得分点
        if (rubricContent.trim()) {
            let rubricLines = rubricContent.trim().split('\n').map(l => l.trim()).filter(l => l);
            let mergedLines = [];
            for (let i = 0; i < rubricLines.length; i++) {
                let line = rubricLines[i];
                if (mergedLines.length > 0 && line.match(/^[（(]\d+\.?\d*分[)）]$/)) { mergedLines[mergedLines.length - 1] += line; }
                else { mergedLines.push(line); }
            }
            rubricLines = mergedLines;
            let extractedPoints = '', extractedRules = '', extractedCount = 0, currentMode = 'rules';
            for (const line of rubricLines) {
                const tl = line.trim();
                if (!tl) continue;
                const isRulesTitle = tl.match(/^(评分规则|评分总则|得分规则|扣分规则|记分规则|总则|规则)[：:\s]*/i);
                const isPointsTitle = tl.match(/^(得分要点|评分要点|分数分布|要点)[：:\s]*/i);
                if (isRulesTitle) { currentMode = 'rules'; extractedRules += tl + '\n'; continue; }
                else if (isPointsTitle) { currentMode = 'points'; extractedRules += tl + '\n'; continue; }
                if (currentMode === 'rules') { extractedRules += tl + '\n'; }
                else {
                    const rm = tl.match(/(.*?)([（(][^)）]*分[^)）]*[)）])/);
                    if (rm) {
                        const c = rm[1].trim(), r = rm[2].trim();
                        if (c) { let p = c.replace(/^\d+[、\.]\s*/, '').replace(/^[一二三四五六七八九十]+、\s*/, ''); const sm = r.match(/(\d+\.?\d*)\s*分/); if (sm) p += ` (${sm[1]}分)`; extractedPoints += p + '\n'; const rt = r.replace(/[（()）]/g, '').replace(/\d+\s*分/, '').trim(); if (rt) extractedRules += r + '\n'; extractedCount++; }
                    } else if (tl.match(/^\d+[、\.]/) || tl.match(/^[一二三四五六七八九十]+、\s*/)) {
                        let p = tl.replace(/^\d+[、\.]\s*/, '').replace(/^[一二三四五六七八九十]+、\s*/, '');
                        const rm2 = p.match(/(.*?)([（(][^)）]*分[^)）]*[)）])/);
                        if (rm2) { const c = rm2[1].trim(), r = rm2[2].trim(); if (c) { const sm = r.match(/(\d+\.?\d*)\s*分/); if (sm) c += ` (${sm[1]}分)`; extractedPoints += c + '\n'; const rt = r.replace(/[（()）]/g, '').replace(/\d+\s*分/, '').trim(); if (rt) extractedRules += r + '\n'; extractedCount++; } }
                        else if (p.includes('分）') || p.includes('分)')) { p = p.replace(/（\s*(\d+\.?\d*)\s*分[^）]*）/g, (m, p1) => { const rt = m.replace(/[（()）\d\s分]/g, '').trim(); if (rt) extractedRules += m + '\n'; return `(${p1}分)`; }); p = p.replace(/\(\s*(\d+\.?\d*)\s*分[^\)]*\)/g, (m, p1) => { const rt = m.replace(/[()\d\s分]/g, '').trim(); if (rt) extractedRules += m + '\n'; return `(${p1}分)`; }); extractedPoints += p + '\n'; extractedCount++; }
                        else if (p.length < 20) { extractedRules += tl + '\n'; }
                        else { extractedPoints += p + '\n'; extractedCount++; }
                    } else if (tl.length < 25 && (tl.includes('分') || tl.includes('分）') || tl.includes('分)'))) { extractedRules += tl + '\n'; }
                    else if (!tl.includes('分') && tl.length < 15) { extractedRules += tl + '\n'; }
                    else { let p = tl.replace(/^\d+[、\.]\s*/, '').replace(/^[一二三四五六七八九十]+、\s*/, ''); if (p.trim()) extractedPoints += p + '\n'; }
                }
            }
            if (extractedPoints.trim()) rubricPoints = extractedPoints.trim();
            if (extractedRules.trim()) { rubricRules = extractedRules.trim(); }
        }

        let aiRubric = aiPromptContent.trim() || '';
        const points = rubricPoints ? rubricPoints.split('\n').filter(l => l.trim()).length : 0;
        const hasAnswer = !!standardAnswer;
        const result = {
            content: content,
            score: score,
            standardAnswer: standardAnswer,
            rubricRules: rubricRules,
            rubricPoints: rubricPoints,
            aiRubric: aiRubric,
            parseResult: {
                maxScore: score,
                points: points,
                hasAnswer: hasAnswer
            }
        };
        return result;
    }

    window.AutoParse = {
        parseChinese: parseChinese,
        parseEnglish: parseEnglish
    };
})();
