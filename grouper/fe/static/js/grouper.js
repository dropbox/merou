$(document).ready(function(){
    $(".public-key").click(function(){
        $("#key-body").text($(this).attr("key-body"));
        $("#key-modal").modal('show');
    });

    $('[data-toggle="popover"]').popover({
        html: true,
        placement: 'auto right',
        container: 'body',
    });
});
