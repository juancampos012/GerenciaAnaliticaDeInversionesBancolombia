// Funciones de apoyo para las gráficas de Apache ECharts

// Formato de números colombiano: 1.234.567,89
function formatNumber(value) {
    return Number(value).toLocaleString("es-CO", { maximumFractionDigits: 2 });
}

// Acorta los nombres largos en los ejes
function shortName(name) {
    return name.length > 32 ? name.slice(0, 32) + "…" : name;
}

// Hace que la gráfica cambie de tamaño con la ventana
function makeResponsive(chart) {
    window.addEventListener("resize", () => chart.resize());
}

// Gráfica de barras horizontales
// prefix: texto antes del valor, por ejemplo "$ " o "US$ "
function barChart(elementId, names, values, prefix = "") {
    const element = document.getElementById(elementId);
    if (!element) return;

    const chart = echarts.init(element);
    chart.setOption({
        tooltip: {
            trigger: "axis",
            axisPointer: { type: "shadow" },
            valueFormatter: (value) => prefix + formatNumber(value),
        },
        grid: { left: 10, right: 30, top: 10, bottom: 10, containLabel: true },
        xAxis: { type: "value", axisLabel: { formatter: (value) => formatNumber(value) } },
        yAxis: {
            type: "category",
            inverse: true,
            data: names,
            axisLabel: { formatter: shortName },
        },
        series: [{ type: "bar", data: values, barMaxWidth: 28, itemStyle: { color: "#2186eb" } }],
    });
    makeResponsive(chart);
}

// Gráfica de dona
// items: lista de { name: "...", value: 123 }
function donutChart(elementId, items, prefix = "") {
    const element = document.getElementById(elementId);
    if (!element) return;

    const chart = echarts.init(element);
    chart.setOption({
        tooltip: {
            trigger: "item",
            formatter: (item) => item.name + "<br>" + prefix + formatNumber(item.value) + " (" + item.percent + " %)",
        },
        legend: { bottom: 0 },
        series: [{
            type: "pie",
            radius: ["45%", "70%"],
            bottom: 30,
            data: items,
            label: { formatter: "{d} %" },
        }],
    });
    makeResponsive(chart);
}
