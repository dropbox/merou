$(function () {
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

    $("select#member").attr("data-placeholder", "Select a user or group").chosen();
    $("select#permission").attr("data-placeholder", "Select a permission").chosen();

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

    // The removeUserModal is generated once per page but could be used for any
    // member being removed. So, when the modal shows up, make sure to populate its
    // text and set its form actions to correspond to the selected user.

    $("#removeUserModal").on("show.bs.modal", function(e) {
        var groupName = $('#removeUserModal').data('group-name');
        var button = $(e.relatedTarget);
        var memberName = button.data("member-name");
        var memberType = button.data("member-type");

        var modal = $(e.currentTarget);
        modal.find(".member-name").html(memberName);

        var form = modal.find(".remove-member-form");
        form.attr("action", "/groups/" + groupName + "/remove");
        form.find("input[name=member]").val(memberName);
        form.find("input[name=member_type]").val(memberType);
    });

    $("#createModal").on("shown.bs.modal", function(){
        $("#groupname").focus();
    });

    $("#formSubmit").click(function() {
        $("#createFrom").submit();
    });

    // The revokeModal is generated once per page but could be used for any member being
    // removed. So, when the modal shows up, make sure to populate its text and set its form
    // actions to correspond to the selected user.

    $("#revokeModal").on("show.bs.modal", function(e) {
        var button = $(e.relatedTarget);
        var group = button.data("group");
        var user = button.data("user");
        var mappingId = button.data("mapping-id");

        var modal = $(e.currentTarget);

        var form = modal.find(".revoke-permission-form");
        form.attr("action", "/groups/" + group + "/service/" + user + "/revoke/" + mappingId);
    });

    var auditModal = $('#auditModal');
    if (auditModal.data('show') === true) {
        auditModal.modal('show');
    }

    $('#permission-request').each(function() {
        $form = $(this);
        var args_by_perm = $form.data('permission');

        var $argument_div = $form.find('.form-group-argument');
        var $reason_div = $form.find('.form-group-reason');

        var $group_input = $form.find('#group_name');
        var $permission_input = $form.find('#permission');
        var $argument_input = $form.find('#argument');

        // Supplement the <input> "argument" field with an adjacent
        // "argument" dropdown that we can fill with permission-specific
        // options.  We use renaming, below, to make sure only one of
        // the two inputs is actually named "argument" when the form
        // submits.
        var $argument_select = $("<select>", {
            "name": $argument_input.attr('name'),
            "class": $argument_input.attr('class'),
        }).insertAfter($argument_input);

        function update() {
            $permission = $permission_input.val()

            if ($permission === "") {
                $argument_div.hide();
                $reason_div.hide();
                return
            }

            $argument_div.show();
            $reason_div.show();

            var args = args_by_perm[$permission];

            if (args.length == 1 && args[0] == "*") {
                $argument_input.show();
                $argument_input.prop('name', 'argument');
                $argument_input.prop('required', false);

                $argument_select.hide();
                $argument_select.prop('name', 'ignore');
                $argument_select.prop('required', false);
            } else {
                $argument_input.hide();
                $argument_input.prop('name', 'ignore');
                $argument_input.prop('required', false);

                $argument_select.show();
                $argument_select.prop('name', 'argument');
                $argument_select.prop('required', true);

                $argument_select.empty();
                $.each(args, function(index, arg) {
                    var option = $("<option></option>").attr("value", arg).text(arg);
                    $argument_select.append(option);
                });
            }
        }

        update();

        $permission_input.on('change', update);
    });

    $("#clickthruModal #agree-clickthru-btn").on("click", function(e) {
        $(".join-group-form .clickthru-checkbox").prop("checked", true);
        $(".join-group-form").submit();
    });

    // The form with id submitOnce disables itself after being clicked and
    // switches the cursor to the progress cursor.
    $('#submitOnce').one('submit', function() {
        $('body').addClass('waiting');
        $(this).addClass('waiting');
        $(this).find(':submit').prop('disabled', true);
    });
});
