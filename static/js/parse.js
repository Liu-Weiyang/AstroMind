        // ===== 段落解析（供展示与详情共用，避免整段文字重复显示） =====
        function deriveShortTitle(text) {
            // 从正文提取短标题：取第一句（到句号/问号/感叹号），最长120字符
            var m = text.match(/^(.{2,120}?)[。．！？.!?]/);
            var t = m ? m[1] : '';
            t = t.replace(/[:：\-–—,，\s]+$/g, '').trim();
            if (t.length < 4) return '';
            return t;
        }

        function parseParagraph(trimmed) {
            var title = '';
            var content = trimmed;
            var titleMatch = trimmed.match(/^\*\*(.*?)\*\*/);
            if (titleMatch) {
                title = titleMatch[1].trim();
                content = trimmed.replace(/^\*\*.*?\*\*/, '').trim();
                // 注意：不要吞掉开头的「- 」项目符号（如「当前关键困难」的第一条 bullet），
                // 只清理冒号/破折号/空白等标题分隔符
                content = content.replace(/^[:：–—\s]+/, '');
            } else {
                var t = deriveShortTitle(trimmed);
                if (t) {
                    // 标题取自正文开头时，把该片段从正文中移除，避免上下重复
                    var rest = trimmed.slice(t.length).replace(/^[。．！？.!?，,：:；;\s]+/, '').trim();
                    // 若标题把整段正文都吃掉了（单句段落），放弃标题，保持正文完整
                    if (rest.length >= 10) {
                        title = t;
                        content = rest;
                    }
                }
            }
            return { title: title, content: content };
        }

        function mergeParagraphs(rawParagraphs) {
            // 整段只有 **小标题** 的段落（如 **观测进展**）与其后的正文段落合并，
            // 避免出现“只有标题的空卡片”以及标题被重复显示。
            var merged = [];
            for (var i = 0; i < rawParagraphs.length; i++) {
                var para = rawParagraphs[i].trim();
                if (/^\*\*[^*]+\*\*$/.test(para)) {
                    if (i + 1 < rawParagraphs.length) {
                        merged.push(para + '\n' + rawParagraphs[i + 1].trim());
                        i++;
                        continue;
                    }
                    // 结尾孤立的纯标题段落：没有正文可合并，直接丢弃，避免空卡片
                    continue;
                }
                merged.push(para);
            }
            return merged;
        }
