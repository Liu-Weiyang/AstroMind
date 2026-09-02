        // ===== 引导系统 =====
        var tutorialBound = false;
        var tutorialStep = 0;
        var tutorialSteps = [];
        var tutorialDots = [];
        function initTutorial() {
            var overlay = document.getElementById('tutorialOverlay');
            if (!tutorialBound) {
                tutorialBound = true;   // 监听只绑定一次，重置引导时只重新显示

                tutorialSteps = Array.prototype.slice.call(document.querySelectorAll('.tutorial-step'));
                tutorialDots = Array.prototype.slice.call(document.querySelectorAll('.tutorial-dots span'));

                function goToStep(index) {
                    tutorialSteps.forEach(function(el, i) {
                        el.classList.toggle('active', i === index);
                    });
                    tutorialDots.forEach(function(el, i) {
                        el.classList.toggle('active', i === index);
                    });
                    tutorialStep = index;
                    // 最后一页时按钮显示「完成」，其它页显示「下一步」
                    var nextBtn = document.getElementById('tutorialNext');
                    if (nextBtn) {
                        nextBtn.textContent = (index >= tutorialSteps.length - 1) ? t('tutorial.finish') : t('tutorial.next');
                    }
                    // 从第二页起显示「上一页」，第一页隐藏
                    var prevBtn = document.getElementById('tutorialPrev');
                    if (prevBtn) {
                        prevBtn.style.display = (index > 0) ? '' : 'none';
                    }
                }
                window._goTutorialStep = goToStep;

                document.getElementById('tutorialNext').addEventListener('click', function() {
                    if (tutorialStep < tutorialSteps.length - 1) {
                        goToStep(tutorialStep + 1);
                    } else {
                        // 完成
                        setLocal('hasSeenTutorial', true);
                        overlay.style.display = 'none';
                    }
                });

                document.getElementById('tutorialSkip').addEventListener('click', function() {
                    setLocal('hasSeenTutorial', true);
                    overlay.style.display = 'none';
                });

                // 「上一页」按钮：回到上一页
                document.getElementById('tutorialPrev').addEventListener('click', function() {
                    if (tutorialStep > 0) {
                        goToStep(tutorialStep - 1);
                    }
                });

                // 点击底部圆点，跳转到对应页
                tutorialDots.forEach(function(dot, i) {
                    dot.addEventListener('click', function() {
                        goToStep(i);
                    });
                });
            }
            // 已看过 → 隐藏；未看过或刚被重置 → 显示（重置后始终从第一页开始）
            if (getLocal('hasSeenTutorial')) {
                overlay.style.display = 'none';
            } else {
                window._goTutorialStep(0);
                overlay.style.display = 'flex';
            }
        }
