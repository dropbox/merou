$(document).ready(function(){
    $(".public-key").click(function(){
        $("#key-body").text($(this).attr("key-body"));
        $("#key-modal").modal('show');
    });

    $('[data-toggle="popover"]').popover({
        html: true,
        placement: 'auto right',
        container: 'body'
    });

    try {
        $('table.datatable').dataTable({
            'searching': false,
            'paging': false,
            'info': false
        });
    } catch(e) {
        console.log("error in datatable init: ", e);
    }
});
