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

    $("#createModal").on("shown.bs.modal", function(){
        $("#groupname").focus();
    });

    $("#formSubmit").click(function() {
        $("#createFrom").submit();
    });

    // The revokeModal is generated once per page but could be used for any member being removed. So,
    // when the modal shows up, make sure to populate its text and set its form actions to correspond to
    // the selected user.

    $("#revokeModal").on("show.bs.modal", function(e) {
        var button = $(e.relatedTarget);
        var mappingId = button.data("mapping-id");

        var modal = $(e.currentTarget);

        var form = modal.find(".revoke-permission-form");
        form.attr("action", "/groups/{{group.name}}/service/{{user.username}}/revoke/" + mappingId);
    });

    var auditModal = $('#auditModal');
    if (auditModal.data('show') === true) {
        auditModal.modal('show');
    }

    var group_perm_request = $('#groupPermissionRequest');
    if (group_perm_request.length)
    {
        var args_by_perm = group_perm_request.data('permission');

        var $reason_divs = $('.form-group-reason');
        var $argument_divs = $('.form-group-argument');

        var $argument_select = $('#dropdown_form #argument');
        var $argument_text = $('#text_form #argument');

        var $dropdown_form_div = $('#dropdown_form');
        var $text_form_div = $('#text_form');

        var $perm_fields = $('.input-permission_name');
        var $reason_fields = $('.input-reason');

        function update_args() {
            var args = args_by_perm[$perm_fields.val()];
            if ($perm_fields.val() == "") {
                // default we show dropdown form (we have to choose one) and
                //    hide argument and reason fields (ux hint to select permission
                //    first)
                $argument_divs.hide();
                $reason_divs.hide();

                $dropdown_form_div.show();
                $text_form_div.hide();
            } else if (args.length == 1 && args[0] == "*") {
                // change to text form field cause permission allows a wildcard argument
                $argument_divs.show();
                $reason_divs.show();

                $dropdown_form_div.hide();
                $text_form_div.show();

                $argument_text.empty();
            } else {
                // change to dropdown form field cause permission only specific
                //    specific arguments #}
                $argument_divs.show();
                $reason_divs.show();

                $dropdown_form_div.show();
                $text_form_div.hide();

                $argument_select.empty();
                $.each(args, function(index, arg) {
                    var option = $("<option></option>").attr("value", arg).text(arg);
                    $argument_select.append(option);
                });
            }
        }

        // prime it
        update_args();

        $perm_fields.change(function() {
            // keep permission values synced
            $perm_fields.val($(this).val());

            // update view of the world
            update_args();
        });

        $reason_fields.keyup(function() {
            // keep reason values synced
            $reason_fields.val($(this).val());
        });
    }

    $('#permission-request').each(function() {
        $form = $(this);
        var args_by_perm = $form.data('permission');
        console.log(args_by_perm);

        var $argument_div = $form.find('.form-group-argument');
        var $reason_div = $form.find('.form-group-reason');

        var $group_input = $form.find('#group_name');
        var $permission_input = $form.find('#permission_name');
        var $argument_input = $form.find('#argument');

        // Supplement the standard <input> field with an adjacent
        // dropdown that we can fill with permission-specific options.
        // We use careful enabling and disabling, below, to make sure
        // only one of the inputs is eligible to be included in the
        // submitted form.
        var $argument_select = $("<select>", {
            "name": $argument_input.attr('name'),
            "class": $argument_input.attr('class'),
        }).insertAfter($argument_input);

        // Helpfully gray out drop-downs that have arrived with only one
        // option, meaning that they have been specified in the URL.
        function disable_if_only_one_option($input) {
            if ($input.find('option').size() == 1)
                $input.prop('disabled', true);
        }
        disable_if_only_one_option($group_input);
        disable_if_only_one_option($permission_input);

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
                $argument_select.hide();

                $argument_input.prop('disabled', false);
                $argument_select.prop('disabled', true);
            } else {
                $argument_input.hide();
                $argument_select.show();

                $argument_input.prop('disabled', true);
                $argument_select.prop('disabled', false);

                $argument_select.empty();
                $.each(args, function(index, arg) {
                    var option = $("<option></option>").attr("value", arg).text(arg);
                    $argument_select.append(option);
                });
            }
        }

        update();

        $permission_input.on('change', update);

        $form.on('submit', function() {
            // Re-enable possibly disabled inputs, so they get transmitted.
            $group_input.prop('disabled', false);
            $permission_input.prop('disabled', false);
        });
    });

    $("#clickthruModal #agree-clickthru-btn").on("click", function(e) {
        $(".join-group-form .clickthru-checkbox").prop("checked", true);
        $(".join-group-form").submit();
    });
});
