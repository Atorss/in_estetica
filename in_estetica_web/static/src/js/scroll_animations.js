(function () {
    'use strict';

    var isFinePointer = window.matchMedia && window.matchMedia('(pointer: fine)').matches;

    // ===== CUSTOM CURSOR =====
    function initCursor() {
        if (!isFinePointer) return;
        if (document.querySelector('.nutri-cursor')) return;

        var cursor = document.createElement('div');
        cursor.className = 'nutri-cursor';
        var dot = document.createElement('div');
        dot.className = 'nutri-cursor__dot';
        document.body.appendChild(cursor);
        document.body.appendChild(dot);
        document.body.classList.add('nutri-cursor-active');

        var mx = window.innerWidth / 2, my = window.innerHeight / 2;
        var cx = mx, cy = my;

        document.addEventListener('mousemove', function (e) {
            mx = e.clientX;
            my = e.clientY;
            dot.style.transform = 'translate(' + (mx - 3) + 'px, ' + (my - 3) + 'px)';
        });

        function loop() {
            cx += (mx - cx) * 0.18;
            cy += (my - cy) * 0.18;
            cursor.style.transform = 'translate(' + (cx - 16) + 'px, ' + (cy - 16) + 'px)';
            requestAnimationFrame(loop);
        }
        loop();

        var hoverTargets = 'a, button, .nutri-card, .nutri-doctor-card, .nutri-pillar-card, .nutri-testimonial, .nutri-infocard, .nutri-btn, .nutri-ba-slider';
        document.body.addEventListener('mouseover', function (e) {
            if (e.target.closest(hoverTargets)) cursor.classList.add('nutri-cursor--hover');
        });
        document.body.addEventListener('mouseout', function (e) {
            if (e.target.closest(hoverTargets)) cursor.classList.remove('nutri-cursor--hover');
        });
        document.addEventListener('mouseleave', function () { cursor.style.opacity = '0'; dot.style.opacity = '0'; });
        document.addEventListener('mouseenter', function () { cursor.style.opacity = '1'; dot.style.opacity = '1'; });
    }

    // ===== CARDS TILT 3D =====
    function initTilt() {
        if (!isFinePointer) return;
        var tiltables = document.querySelectorAll('.nutri-card, .nutri-doctor-card, .nutri-testimonial');
        tiltables.forEach(function (card) {
            card.style.transformStyle = 'preserve-3d';
            card.style.willChange = 'transform';

            card.addEventListener('mousemove', function (e) {
                var rect = card.getBoundingClientRect();
                var px = (e.clientX - rect.left) / rect.width;
                var py = (e.clientY - rect.top) / rect.height;
                var rx = (py - 0.5) * -8;
                var ry = (px - 0.5) * 8;
                card.style.transform = 'perspective(900px) rotateX(' + rx + 'deg) rotateY(' + ry + 'deg) translateY(-8px)';
            });
            card.addEventListener('mouseleave', function () {
                card.style.transform = '';
            });
        });
    }

    // ===== SPLIT TEXT HERO =====
    function initSplitText() {
        var title = document.querySelector('.nutri-hero__title');
        if (!title || title.dataset.split) return;
        title.dataset.split = '1';

        function escapeChar(ch) {
            if (ch === '<') return '&lt;';
            if (ch === '>') return '&gt;';
            if (ch === '&') return '&amp;';
            return ch;
        }

        var temp = document.createElement('div');
        temp.innerHTML = title.innerHTML;
        var out = '';
        temp.childNodes.forEach(function (node) {
            if (node.nodeType === 3) {
                var text = node.textContent;
                var words = text.split(/(\s+)/);
                words.forEach(function (w) {
                    if (!w) return;
                    if (/^\s+$/.test(w)) {
                        out += ' ';
                        return;
                    }
                    var chars = '';
                    for (var i = 0; i < w.length; i++) {
                        chars += '<span class="nutri-char">' + escapeChar(w[i]) + '</span>';
                    }
                    out += '<span class="nutri-word">' + chars + '</span>';
                });
            } else if (node.nodeName === 'BR') {
                out += '<br/>';
            } else {
                out += node.outerHTML;
            }
        });
        title.innerHTML = out;

        var chars = title.querySelectorAll('.nutri-char');
        chars.forEach(function (c, i) {
            c.style.opacity = '0';
            c.style.transform = 'translateY(40px) rotate(4deg)';
            c.style.transition = 'opacity 0.7s cubic-bezier(0.2, 0.6, 0.2, 1) ' + (i * 0.03 + 0.2) + 's, transform 0.7s cubic-bezier(0.2, 0.6, 0.2, 1) ' + (i * 0.03 + 0.2) + 's';
        });
        setTimeout(function () {
            chars.forEach(function (c) {
                c.style.opacity = '1';
                c.style.transform = 'translateY(0) rotate(0)';
            });
        }, 80);
    }

    // ===== CLIP-PATH REVEAL =====
    function initClipReveal() {
        var revealables = document.querySelectorAll(
            '.nutri-card__image, .nutri-pillar-card__img, .nutri-doctor-card__photo, .nutri-about__image'
        );
        if (!('IntersectionObserver' in window)) return;
        revealables.forEach(function (el) {
            el.style.clipPath = 'inset(100% 0 0 0)';
            el.style.transition = 'clip-path 1.1s cubic-bezier(0.7, 0, 0.2, 1)';
        });
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.style.clipPath = 'inset(0 0 0 0)';
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.15 });
        revealables.forEach(function (el) { observer.observe(el); });
    }

    // ===== SCROLL FADE (cards / sections) =====
    function initScrollAnimations() {
        var wrap = document.querySelector('.nutri-home');
        if (!wrap) return;

        var selectors = [
            '.nutri-card',
            '.nutri-pillar-card',
            '.nutri-doctor-card',
            '.nutri-testimonial',
            '.nutri-section__header',
            '.nutri-quote__inner',
            '.nutri-infocard',
            '.nutri-step',
            '.nutri-contact-card',
            '.nutri-ba-slider'
        ];

        var elements = wrap.querySelectorAll(selectors.join(','));
        if (!elements.length) return;

        elements.forEach(function (el) {
            el.style.opacity = '0';
            el.style.transform = 'translateY(40px)';
            el.style.transition = 'opacity 0.7s ease, transform 0.7s ease';

            var col = el.closest('[class*="col-"]');
            if (col && col.parentElement) {
                var cols = col.parentElement.children;
                for (var i = 0; i < cols.length; i++) {
                    if (cols[i] === col) {
                        el.style.transitionDelay = (i * 0.1) + 's';
                        break;
                    }
                }
            }
        });

        // Hero badge, accent, desc, cta
        var heroBadge = wrap.querySelector('.nutri-hero__badge');
        var heroAccent = wrap.querySelector('.nutri-hero__accent');
        var heroDesc = wrap.querySelector('.nutri-hero__desc');
        var heroCta = wrap.querySelector('.nutri-hero__cta');

        var heroEls = [
            { el: heroBadge, delay: 0 },
            { el: heroAccent, delay: 1.4 },
            { el: heroDesc, delay: 1.6 },
            { el: heroCta, delay: 1.8 },
        ];

        heroEls.forEach(function (item) {
            if (!item.el) return;
            item.el.style.opacity = '0';
            item.el.style.transform = 'translateY(30px)';
            item.el.style.transition = 'opacity 0.9s ease ' + item.delay + 's, transform 0.9s ease ' + item.delay + 's';
        });

        setTimeout(function () {
            heroEls.forEach(function (item) {
                if (!item.el) return;
                item.el.style.opacity = '1';
                item.el.style.transform = 'translateY(0)';
            });
        }, 100);

        if ('IntersectionObserver' in window) {
            var observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.style.opacity = '1';
                        entry.target.style.transform = 'translateY(0)';
                        observer.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
            elements.forEach(function (el) { observer.observe(el); });
        } else {
            elements.forEach(function (el) {
                el.style.opacity = '1';
                el.style.transform = 'translateY(0)';
            });
        }
    }

    // ===== HERO SLIDESHOW =====
    function initSlideshow() {
        var slides = document.querySelectorAll('.nutri-hero__slide');
        if (slides.length < 2) return;
        var current = 0;
        var interval = 3000;
        setInterval(function () {
            slides[current].classList.remove('nutri-hero__slide--active');
            slides[current].style.transform = 'scale(1)';
            current = (current + 1) % slides.length;
            slides[current].classList.add('nutri-hero__slide--active');
        }, interval);
    }

    // ===== COUNTERS =====
    function initCounters() {
        var stats = document.querySelectorAll('.nutri-stat__num');
        if (!stats.length || !('IntersectionObserver' in window)) return;
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                var el = entry.target;
                var text = el.textContent.trim();
                var match = text.match(/(\d+)([\D]*)$/);
                if (!match) return;
                var target = parseInt(match[1], 10);
                var suffix = match[2] || '';
                var duration = 1500;
                var start = performance.now();
                function tick(now) {
                    var progress = Math.min((now - start) / duration, 1);
                    var eased = 1 - Math.pow(1 - progress, 3);
                    el.textContent = Math.floor(target * eased) + suffix;
                    if (progress < 1) requestAnimationFrame(tick);
                    else el.textContent = target + suffix;
                }
                requestAnimationFrame(tick);
                observer.unobserve(el);
            });
        }, { threshold: 0.5 });
        stats.forEach(function (s) { observer.observe(s); });
    }

    // ===== BEFORE / AFTER SLIDER =====
    function initBeforeAfter() {
        var sliders = document.querySelectorAll('.nutri-ba-slider');
        sliders.forEach(function (slider) {
            var handle = slider.querySelector('.nutri-ba-slider__handle');
            var after = slider.querySelector('.nutri-ba-slider__after');
            if (!handle || !after) return;

            var dragging = false;
            var pos = 50;

            function setPos(p) {
                pos = Math.max(0, Math.min(100, p));
                after.style.clipPath = 'inset(0 0 0 ' + pos + '%)';
                handle.style.left = pos + '%';
            }

            setPos(50);

            function getX(e) {
                var rect = slider.getBoundingClientRect();
                var clientX = e.touches ? e.touches[0].clientX : e.clientX;
                return ((clientX - rect.left) / rect.width) * 100;
            }

            function start(e) { dragging = true; setPos(getX(e)); e.preventDefault(); }
            function move(e) { if (!dragging) return; setPos(getX(e)); }
            function end() { dragging = false; }

            slider.addEventListener('mousedown', start);
            slider.addEventListener('touchstart', start, { passive: false });
            window.addEventListener('mousemove', move);
            window.addEventListener('touchmove', move, { passive: false });
            window.addEventListener('mouseup', end);
            window.addEventListener('touchend', end);

            // Hint: pulse handle on first appearance
            if ('IntersectionObserver' in window) {
                var observer = new IntersectionObserver(function (entries) {
                    entries.forEach(function (entry) {
                        if (entry.isIntersecting) {
                            slider.classList.add('nutri-ba-slider--visible');
                            // Auto demo
                            var seq = [30, 70, 50];
                            seq.forEach(function (p, i) {
                                setTimeout(function () { setPos(p); }, 500 + i * 600);
                            });
                            observer.unobserve(entry.target);
                        }
                    });
                }, { threshold: 0.4 });
                observer.observe(slider);
            }
        });
    }

    function boot() {
        initCursor();
        initTilt();
        initSplitText();
        initClipReveal();
        initScrollAnimations();
        initSlideshow();
        initCounters();
        initBeforeAfter();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        setTimeout(boot, 200);
    }

    window.addEventListener('load', function () {
        setTimeout(boot, 300);
    });
})();
