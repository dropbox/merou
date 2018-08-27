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

$(function () {
    $("select#member")
    .attr("data-placeholder", "Select a user or group")
    .chosen();

    $('#add-form-expiration').datetimepicker({
        pickTime: false,
        icons: {
            time: "fa fa-clock-o",
            date: "fa fa-calendar",
            up: "fa fa-arrow-up",
            down: "fa fa-arrow-down"
        },
        useCurrent: false,
        minDate: moment(),
    });
});

$(function () {
    $('#audit-form-ends-at').datetimepicker({
        pickTime: false,
        icons: {
            time: "fa fa-clock-o",
            date: "fa fa-calendar",
            up: "fa fa-arrow-up",
            down: "fa fa-arrow-down"
        },
        useCurrent: false,
        minDate: moment(),
    });
});

$(function () {
    $('#edit-form-expiration').datetimepicker({
        pickTime: false,
        icons: {
            time: "fa fa-clock-o",
            date: "fa fa-calendar",
            up: "fa fa-arrow-up",
            down: "fa fa-arrow-down"
        },
        useCurrent: false,
        minDate: moment(),
    });
});

$(function () {
    $('#join-form-expiration').datetimepicker({
        pickTime: false,
        icons: {
            time: "fa fa-clock-o",
            date: "fa fa-calendar",
            up: "fa fa-arrow-up",
            down: "fa fa-arrow-down"
        },
        useCurrent: false,
        minDate: moment(),
    });
});

// The removeUserModal is generated once per page but could be used for any
// member being removed. So, when the modal shows up, make sure to populate its
// text and set its form actions to correspond to the selected user.
$(function () {
    $("#removeUserModal").on("show.bs.modal", function(e) {
        var groupId = $('#removeUserModal').data('group-id');
        var button = $(e.relatedTarget);
        var memberName = button.data("member-name");
        var memberType = button.data("member-type");

        var modal = $(e.currentTarget);
        modal.find(".member-name").html(memberName);

        var form = modal.find(".remove-member-form");
        form.attr("action", "/groups/" + groupId + "/remove");
        form.find("input[name=member]").val(memberName);
        form.find("input[name=member_type]").val(memberType);
    });
});

$(function(){

    $("#createModal").on("shown.bs.modal", function(){
        $("#groupname").focus();
    });
    $("#formSubmit").click(function() {
        $("#createFrom").submit();
    });
});

// The revokeModal is generated once per page but could be used for any member being removed. So,
// when the modal shows up, make sure to populate its text and set its form actions to correspond to
// the selected user.
$(function () {
    $("#revokeModal").on("show.bs.modal", function(e) {
        var button = $(e.relatedTarget);
        var mappingId = button.data("mapping-id");

        var modal = $(e.currentTarget);

        var form = modal.find(".revoke-permission-form")
        form.attr("action", "/groups/{{group.name}}/service/{{user.username}}/revoke/" + mappingId);
    });
});

$(function(){

    $("#createModal").on("shown.bs.modal", function(){
        $("#tagname").focus();
    });
    $("#formSubmit").click(function() {
        $("#createFrom").submit();
    });
});