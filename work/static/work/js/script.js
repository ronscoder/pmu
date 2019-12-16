function tdcss() {
    $(document).ready(function () {
        $("td").each(function (i) {
            // 
            isNumber = parseFloat($(this).text())
            if (!isNaN(isNumber))
                $(this).css('text-align', 'right');
            if ($(this).text() < 0)
                $(this).css({ "color": "red", "background-color": "rgb(243, 220, 220)" });
            //$(this).css({"background-color":"red"});
        });
    });
}
tdcss();