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

    $("#createModal").on("shown.bs.modal", function(){
        $("#tagname").focus();
    });

    $("#revokeModal").on("show.bs.modal", function(e) {
        var button = $(e.relatedTarget);
        var mappingId = button.data("mapping-id");

        var modal = $(e.currentTarget);

        var form = modal.find(".revoke-permission-form");
        form.attr("action", "/groups/{{group.name}}/service/{{user.username}}/revoke/" + mappingId);
    });

    $("#removeUserModal").on("show.bs.modal", function(e) {
        var button = $(e.relatedTarget);
        var memberName = button.data("member-name");
        var memberType = button.data("member-type");
        var groupId = $('#removeUserModal').data('group-id');

        var modal = $(e.currentTarget);
        modal.find(".member-name").html(memberName);

        var form = modal.find(".remove-member-form");
        form.attr("action", "/groups/" + groupId + "/remove");
        form.find("input[name=member]").val(memberName);
        form.find("input[name=member_type]").val(memberType);
    });

    $("select#member").attr("data-placeholder", "Select a user or group").chosen();

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

    $("#formSubmit").click(function() {
        $("#createFrom").submit();
    });

    var auditModel = $('#auditModal');

    if (auditModel &&
        auditModel.data('group-auditing') === 'True' &&
        auditModel.data('group-owner') === 'True') {

        auditModel.modal('show');
    }

    if ($('.permission-request')) {
        var reason_divs = $('.form-group-reason');
        var argument_divs = $('.form-group-argument');

        var argument_select = $('#dropdown_form #argument');
        var argument_text = $('#text_form #argument');

        var dropdown_form_div = $('#dropdown_form');
        var text_form_div = $('#text_form');

        var perm_fields = $('.input-permission_name');
        var reason_fields = $('.input-reason');

        function update_args() {
            var args_by_perm = $('.permission-request').data('permission-request');

            if (typeof(args_by_perm) === 'undefined') {
                return;
            }

            var args = args_by_perm[perm_fields.val()];
            if (perm_fields.val() === "") {
                // default we show dropdown form (we have to choose one) and
                //    hide argument and reason fields (ux hint to select permission
                //    first)
                argument_divs.hide();
                reason_divs.hide();

                dropdown_form_div.show();
                text_form_div.hide();
            } else if (args.length == 1 && args[0] === "*") {
                // change to text form field cause permission allows a wildcard argument
                argument_divs.show();
                reason_divs.show();

                dropdown_form_div.hide();
                text_form_div.show();

                argument_text.empty();
            } else {
                // change to dropdown form field cause permission only specific
                //   specific arguments
                argument_divs.show();
                reason_divs.show();

                dropdown_form_div.show();
                text_form_div.hide();

                argument_select.empty();
                $.each(args, function(index, arg) {
                    var option = $("<option></option>").attr("value", arg).text(arg);
                    argument_select.append(option);
                });
            }
        }

        // prime it
        update_args();

        perm_fields.change(function() {
            // keep permission values synced
            perm_fields.val($(this).val());

            // update view of the world
            update_args();
        });

        reason_fields.keyup(function() {
            // keep reason values synced
            reason_fields.val($(this).val());
        });
    }
});
