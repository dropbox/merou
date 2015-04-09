$(document).ready(function(){
    $(".public-key").click(function(){
        $("#key-body").text($(this).attr("key-body"));
        $("#key-modal").modal('show');
    });
});
