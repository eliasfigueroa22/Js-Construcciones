{% macro clean_percentage(column_name) %}
    case
        when {{ column_name }} is null then null
        when typeof({{ column_name }}) = 'VARCHAR' then
            cast(replace(cast({{ column_name }} as varchar), '%', '') as decimal(5,4)) / 100.0
        else cast({{ column_name }} as decimal(5,4))
    end
{% endmacro %}
