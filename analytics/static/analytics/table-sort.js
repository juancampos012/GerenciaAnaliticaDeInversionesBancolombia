// Ordena las tablas con clase "sortable" al hacer clic en un encabezado.
// Las celdas pueden tener data-value con el valor real para ordenar.
// Los encabezados con clase "number" se ordenan como números.

document.querySelectorAll("table.sortable").forEach((table) => {
    const headers = table.querySelectorAll("thead th");

    headers.forEach((header, index) => {
        header.addEventListener("click", () => {
            const tbody = table.querySelector("tbody");
            const rows = Array.from(tbody.querySelectorAll("tr"));
            const isNumber = header.classList.contains("number");

            // Si la columna ya estaba de menor a mayor, se invierte
            const ascending = !header.classList.contains("asc");
            headers.forEach((th) => th.classList.remove("asc", "desc"));
            header.classList.add(ascending ? "asc" : "desc");

            // Valor de una celda para comparar
            const getValue = (row) => {
                const cell = row.children[index];
                const text = cell.dataset.value ?? cell.textContent.trim();
                if (!isNumber) return text.toLowerCase();
                // Las celdas vacías quedan como el valor más pequeño
                return text === "" ? -Infinity : parseFloat(text);
            };

            rows.sort((a, b) => {
                const x = getValue(a);
                const y = getValue(b);
                if (x < y) return ascending ? -1 : 1;
                if (x > y) return ascending ? 1 : -1;
                return 0;
            });

            rows.forEach((row) => tbody.appendChild(row));
        });
    });
});
