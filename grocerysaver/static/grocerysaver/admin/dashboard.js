(function () {
    function getDashboardData() {
        const node = document.getElementById('grocery-dashboard-data');
        if (!node) {
            return null;
        }
        return JSON.parse(node.textContent);
    }

    function setupCanvas(canvas) {
        const rect = canvas.getBoundingClientRect();
        const ratio = window.devicePixelRatio || 1;
        canvas.width = Math.max(1, Math.floor(rect.width * ratio));
        canvas.height = Math.max(1, Math.floor(canvas.height * ratio));
        const ctx = canvas.getContext('2d');
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        return { ctx, width: rect.width, height: canvas.height / ratio };
    }

    function drawLegend(ctx, labels, colors, x, y, maxWidth) {
        ctx.font = '12px "Segoe UI", sans-serif';
        let offsetX = x;
        let offsetY = y;

        labels.forEach((label, index) => {
            const labelWidth = ctx.measureText(label).width + 26;
            if (offsetX + labelWidth > maxWidth) {
                offsetX = x;
                offsetY += 22;
            }

            ctx.fillStyle = colors[index];
            ctx.beginPath();
            ctx.arc(offsetX + 6, offsetY - 4, 6, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = '#b9c7d8';
            ctx.fillText(label, offsetX + 18, offsetY);
            offsetX += labelWidth;
        });
    }

    function drawDonutChart(canvas, config) {
        const { ctx, width, height } = setupCanvas(canvas);
        const total = config.values.reduce((sum, value) => sum + value, 0);
        const centerX = width / 2;
        const centerY = height / 2 + 10;
        const radius = Math.min(width, height) * 0.28;
        const lineWidth = Math.max(24, radius * 0.38);
        let startAngle = -Math.PI / 2;

        ctx.clearRect(0, 0, width, height);
        drawLegend(ctx, config.labels, config.colors, 28, 28, width - 28);

        if (!total) {
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.22)';
            ctx.lineWidth = lineWidth;
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
            ctx.stroke();

            ctx.fillStyle = '#d7e2ee';
            ctx.font = '700 28px "Segoe UI", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('0', centerX, centerY + 8);
            ctx.font = '12px "Segoe UI", sans-serif';
            ctx.fillStyle = '#8da3bf';
            ctx.fillText('Sin datos', centerX, centerY + 28);
            return;
        }

        config.values.forEach((value, index) => {
            const slice = (value / total) * Math.PI * 2;
            ctx.beginPath();
            ctx.strokeStyle = config.colors[index];
            ctx.lineWidth = lineWidth;
            ctx.lineCap = 'round';
            ctx.arc(centerX, centerY, radius, startAngle, startAngle + slice);
            ctx.stroke();
            startAngle += slice;
        });

        ctx.fillStyle = '#f8fbff';
        ctx.font = '700 30px "Segoe UI", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(String(total), centerX, centerY + 8);
        ctx.font = '12px "Segoe UI", sans-serif';
        ctx.fillStyle = '#8da3bf';
        ctx.fillText('ofertas', centerX, centerY + 28);
    }
    function drawHorizontalBars(canvas, config) {
        const { ctx, width, height } = setupCanvas(canvas);
        const left = 110;
        const right = 24;
        const top = 42;
        const bottom = 24;
        const innerWidth = Math.max(10, width - left - right);
        const innerHeight = Math.max(10, height - top - bottom);
        const maxValue = Math.max(...config.values, 1);
        const rowHeight = innerHeight / Math.max(config.labels.length, 1);

        ctx.clearRect(0, 0, width, height);
        drawLegend(ctx, config.labels.slice(0, 3), config.colors, 18, 22, width - 18);

        ctx.font = '12px "Segoe UI", sans-serif';
        ctx.textBaseline = 'middle';

        config.labels.forEach((label, index) => {
            const y = top + index * rowHeight + rowHeight * 0.5;
            const barHeight = Math.min(28, rowHeight * 0.56);
            const barWidth = (config.values[index] / maxValue) * innerWidth;

            ctx.fillStyle = '#b9c7d8';
            ctx.textAlign = 'left';
            ctx.fillText(label, 18, y);

            ctx.fillStyle = 'rgba(148, 163, 184, 0.12)';
            ctx.fillRect(left, y - barHeight / 2, innerWidth, barHeight);

            ctx.fillStyle = config.colors[index % config.colors.length];
            ctx.beginPath();
            ctx.roundRect(left, y - barHeight / 2, Math.max(6, barWidth), barHeight, 8);
            ctx.fill();

            ctx.fillStyle = '#f8fbff';
            ctx.textAlign = 'right';
            ctx.fillText(String(config.values[index]), width - 8, y);
        });
    }

    function drawLineChart(canvas, config) {
        const { ctx, width, height } = setupCanvas(canvas);
        const left = 48;
        const right = 22;
        const top = 28;
        const bottom = 42;
        const innerWidth = Math.max(10, width - left - right);
        const innerHeight = Math.max(10, height - top - bottom);
        const allValues = config.series.flatMap((series) => series.values);
        const maxValue = Math.max(...allValues, 1);

        ctx.clearRect(0, 0, width, height);

        for (let step = 0; step <= 4; step += 1) {
            const y = top + (innerHeight / 4) * step;
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.12)';
            ctx.beginPath();
            ctx.moveTo(left, y);
            ctx.lineTo(width - right, y);
            ctx.stroke();
        }

        config.labels.forEach((label, index) => {
            const x = left + (innerWidth / Math.max(config.labels.length - 1, 1)) * index;
            ctx.fillStyle = '#8da3bf';
            ctx.font = '11px "Segoe UI", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(label, x, height - 14);
        });

        drawLegend(
            ctx,
            config.series.map((series) => series.label),
            config.series.map((series) => series.stroke),
            left,
            18,
            width - right
        );

        config.series.forEach((series) => {
            const points = series.values.map((value, index) => {
                const x = left + (innerWidth / Math.max(series.values.length - 1, 1)) * index;
                const y = top + innerHeight - (value / maxValue) * innerHeight;
                return { x, y, value };
            });

            ctx.beginPath();
            ctx.moveTo(points[0].x, top + innerHeight);
            points.forEach((point) => ctx.lineTo(point.x, point.y));
            ctx.lineTo(points[points.length - 1].x, top + innerHeight);
            ctx.closePath();
            ctx.fillStyle = series.fill;
            ctx.fill();

            ctx.beginPath();
            points.forEach((point, index) => {
                if (index === 0) {
                    ctx.moveTo(point.x, point.y);
                } else {
                    ctx.lineTo(point.x, point.y);
                }
            });
            ctx.strokeStyle = series.stroke;
            ctx.lineWidth = 3;
            ctx.stroke();

            points.forEach((point) => {
                ctx.fillStyle = series.stroke;
                ctx.beginPath();
                ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
                ctx.fill();
            });
        });
    }

    function renderDashboardCharts() {
        const data = getDashboardData();
        if (!data) {
            return;
        }

        const offersChart = document.getElementById('offersChart');
        const categoriesChart = document.getElementById('categoriesChart');
        const activityChart = document.getElementById('activityChart');
        const storesChart = document.getElementById('storesChart');

        if (offersChart) {
            drawDonutChart(offersChart, data.offers);
        }
        if (categoriesChart) {
            drawHorizontalBars(categoriesChart, data.categories);
        }
        if (activityChart) {
            drawLineChart(activityChart, data.activity);
        }
        if (storesChart) {
            drawHorizontalBars(storesChart, data.stores);
        }
    }

    document.addEventListener('DOMContentLoaded', renderDashboardCharts);
    window.addEventListener('resize', renderDashboardCharts);
})();


